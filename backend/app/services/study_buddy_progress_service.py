"""
Study Buddy Progress & Adaptive Planner Service

Orchestrates:
1. Student learning progress metrics derived from persisted quiz attempts.
2. Transparent weak-area identification requiring evidence (>= 2 attempts/questions).
3. Adaptive syllabus-grounded study plan generation with feasibility validation.
4. Task completion tracking, schedule distribution, and plan regeneration.
5. Strict student ownership and institutional department isolation.
"""

import logging
from datetime import datetime, timezone, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from fastapi import HTTPException, status

from ..models.user import User, UserRole
from ..models.study_buddy import (
    Subject,
    SyllabusDocument,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusReviewStatus,
    QuizStatus,
    StudyBuddyQuizAttempt,
    PlanStatus,
    StudyBuddyPlan,
    StudyBuddyPlanTask
)
from ..schemas.study_buddy import (
    StudentProgressDashboardResponse,
    SubjectPerformanceSummary,
    WeakTopicSummary,
    ActivityHistoryItem,
    ActivePlanSummary,
    StudyBuddyQuizAttemptSummaryResponse,
    StudyBuddyPlanResponse,
    StudyBuddyPlanTaskResponse,
    StudyBuddyPlanCreateRequest,
    StudyBuddyPlanUpdateRequest
)

logger = logging.getLogger(__name__)


def _normalize_dept(dept: Optional[str]) -> str:
    """Normalize department strings for case-insensitive comparison."""
    return (dept or "").strip().lower()


def _get_user_department(user: User) -> Optional[str]:
    """Resolve department for user across roles (including student profile branch)."""
    if user.department:
        return user.department
    if user.student_profile and user.student_profile.branch:
        return user.student_profile.branch
    return None


class StudyBuddyProgressService:
    """
    Service for calculating student progress metrics and managing adaptive study plans.
    """

    # =========================================================================
    # 1. STUDENT PROGRESS DASHBOARD METRICS
    # =========================================================================

    def get_student_dashboard_progress(
        self,
        db: Session,
        current_user: User
    ) -> StudentProgressDashboardResponse:
        """
        Derive learning progress metrics strictly from persisted PostgreSQL records.
        Handles zero attempts, incomplete attempts, and limited history gracefully.
        """
        # 1. Fetch all quiz attempts for student
        attempts = (
            db.query(StudyBuddyQuizAttempt)
            .filter(StudyBuddyQuizAttempt.student_id == current_user.id)
            .order_by(desc(StudyBuddyQuizAttempt.created_at))
            .all()
        )

        quizzes_attempted = len(attempts)
        completed_attempts = [a for a in attempts if a.status == QuizStatus.COMPLETED and a.percentage is not None]
        quizzes_completed = len(completed_attempts)

        # Average percentage (None if 0 completed)
        average_percentage: Optional[float] = None
        if quizzes_completed > 0:
            avg_val = sum(a.percentage for a in completed_attempts) / quizzes_completed
            average_percentage = round(avg_val, 1)

        # Most recent quiz attempt summary
        most_recent_quiz: Optional[StudyBuddyQuizAttemptSummaryResponse] = None
        if attempts:
            latest = attempts[0]
            most_recent_quiz = StudyBuddyQuizAttemptSummaryResponse(
                id=latest.id,
                subject_id=latest.subject_id,
                subject_code=latest.subject.code if latest.subject else "",
                subject_name=latest.subject.name if latest.subject else "",
                syllabus_version=latest.syllabus_version,
                title=latest.title,
                difficulty=latest.difficulty,
                status=latest.status.value,
                score=latest.score,
                max_score=latest.max_score,
                percentage=latest.percentage,
                total_questions=latest.total_questions,
                created_at=latest.created_at,
                submitted_at=latest.submitted_at
            )

        # 2. Subject-wise performance breakdown
        subject_attempts_map: Dict[int, List[StudyBuddyQuizAttempt]] = {}
        for a in attempts:
            subject_attempts_map.setdefault(a.subject_id, []).append(a)

        subject_performances: List[SubjectPerformanceSummary] = []
        for subj_id, subj_atts in subject_attempts_map.items():
            first_att = subj_atts[0]
            subj = first_att.subject or db.query(Subject).get(subj_id)
            if not subj:
                continue

            comp_subj_atts = [a for a in subj_atts if a.status == QuizStatus.COMPLETED and a.percentage is not None]
            subj_avg_score: Optional[float] = None
            subj_avg_pct: Optional[float] = None
            latest_comp_date: Optional[datetime] = None

            if comp_subj_atts:
                subj_avg_score = round(sum(a.score or 0.0 for a in comp_subj_atts) / len(comp_subj_atts), 1)
                subj_avg_pct = round(sum(a.percentage for a in comp_subj_atts) / len(comp_subj_atts), 1)
                latest_comp_date = comp_subj_atts[0].submitted_at or comp_subj_atts[0].created_at

            subject_performances.append(
                SubjectPerformanceSummary(
                    subject_id=subj.id,
                    subject_code=subj.code,
                    subject_name=subj.name,
                    quizzes_attempted=len(subj_atts),
                    quizzes_completed=len(comp_subj_atts),
                    average_score=subj_avg_score,
                    average_percentage=subj_avg_pct,
                    latest_quiz_date=latest_comp_date
                )
            )

        # 3. Recent attempts (last 10)
        recent_attempts: List[StudyBuddyQuizAttemptSummaryResponse] = []
        for a in attempts[:10]:
            recent_attempts.append(
                StudyBuddyQuizAttemptSummaryResponse(
                    id=a.id,
                    subject_id=a.subject_id,
                    subject_code=a.subject.code if a.subject else "",
                    subject_name=a.subject.name if a.subject else "",
                    syllabus_version=a.syllabus_version,
                    title=a.title,
                    difficulty=a.difficulty,
                    status=a.status.value,
                    score=a.score,
                    max_score=a.max_score,
                    percentage=a.percentage,
                    total_questions=a.total_questions,
                    created_at=a.created_at,
                    submitted_at=a.submitted_at
                )
            )

        # 4. Learning activity over time (grouped by date of submission/creation)
        activity_map: Dict[str, List[float]] = {}
        for a in completed_attempts:
            dt = a.submitted_at or a.created_at
            if dt:
                date_str = dt.strftime("%Y-%m-%d")
                activity_map.setdefault(date_str, []).append(a.percentage or 0.0)

        activity_history: List[ActivityHistoryItem] = []
        for d_str in sorted(activity_map.keys()):
            pcts = activity_map[d_str]
            activity_history.append(
                ActivityHistoryItem(
                    date=d_str,
                    count=len(pcts),
                    average_percentage=round(sum(pcts) / len(pcts), 1)
                )
            )

        # 5. Weak Topics Calculation (Strict Transparent Rule)
        # Rule: Requires at least 2 questions or completed quiz attempts covering the unit/topic.
        # Accuracy < 60% classifies it as a weak area. Single results are never used to claim weakness.
        weak_topics = self._calculate_weak_topics(db, completed_attempts)

        # 6. Active Study Plan & Task Stats
        active_plan = (
            db.query(StudyBuddyPlan)
            .filter(
                StudyBuddyPlan.student_id == current_user.id,
                StudyBuddyPlan.status == PlanStatus.ACTIVE
            )
            .order_by(desc(StudyBuddyPlan.updated_at), desc(StudyBuddyPlan.created_at))
            .first()
        )

        active_plan_summary: Optional[ActivePlanSummary] = None
        if active_plan:
            prog_pct = 0.0
            if active_plan.total_tasks > 0:
                prog_pct = round((active_plan.completed_tasks / active_plan.total_tasks) * 100.0, 1)

            active_plan_summary = ActivePlanSummary(
                plan_id=active_plan.id,
                title=active_plan.title,
                subject_id=active_plan.subject_id,
                subject_code=active_plan.subject.code if active_plan.subject else "",
                subject_name=active_plan.subject.name if active_plan.subject else "",
                status=active_plan.status.value,
                target_date=active_plan.target_date,
                daily_budget_minutes=active_plan.daily_budget_minutes,
                total_tasks=active_plan.total_tasks,
                completed_tasks=active_plan.completed_tasks,
                progress_percentage=prog_pct
            )

        # Aggregate task stats across all plans for this student
        total_tasks_count = (
            db.query(func.count(StudyBuddyPlanTask.id))
            .join(StudyBuddyPlan, StudyBuddyPlanTask.plan_id == StudyBuddyPlan.id)
            .filter(StudyBuddyPlan.student_id == current_user.id)
            .scalar() or 0
        )
        completed_tasks_count = (
            db.query(func.count(StudyBuddyPlanTask.id))
            .join(StudyBuddyPlan, StudyBuddyPlanTask.plan_id == StudyBuddyPlan.id)
            .filter(
                StudyBuddyPlan.student_id == current_user.id,
                StudyBuddyPlanTask.is_completed == True
            )
            .scalar() or 0
        )
        pending_tasks_count = max(0, total_tasks_count - completed_tasks_count)

        return StudentProgressDashboardResponse(
            quizzes_attempted=quizzes_attempted,
            quizzes_completed=quizzes_completed,
            average_percentage=average_percentage,
            most_recent_quiz=most_recent_quiz,
            subject_performances=subject_performances,
            recent_attempts=recent_attempts,
            activity_history=activity_history,
            weak_topics=weak_topics,
            active_plan=active_plan_summary,
            plan_task_stats={
                "total": total_tasks_count,
                "completed": completed_tasks_count,
                "pending": pending_tasks_count
            }
        )

    def _calculate_weak_topics(
        self,
        db: Session,
        completed_attempts: List[StudyBuddyQuizAttempt]
    ) -> List[WeakTopicSummary]:
        """
        Evaluate weak units and topics strictly using question-level and quiz-level accuracy.
        Enforces evidence requirement: >= 2 questions evaluated to claim weakness.
        """
        # Key: (subject_id, unit_id, topic_id) -> { "correct": int, "total": int, "attempts": set() }
        topic_stats: Dict[Tuple[int, Optional[int], Optional[int]], Dict[str, Any]] = {}

        for attempt in completed_attempts:
            # If attempt has questions_data and student_answers
            q_data = attempt.questions_data or []
            s_answers = attempt.student_answers or {}

            if isinstance(q_data, list) and q_data:
                for idx, q in enumerate(q_data):
                    prov = q.get("provenance") or {}
                    u_id = prov.get("unit_id") or attempt.unit_id
                    t_id = prov.get("topic_id") or attempt.topic_id
                    key = (attempt.subject_id, u_id, t_id)

                    if key not in topic_stats:
                        topic_stats[key] = {"correct": 0, "total": 0, "attempts": set()}

                    topic_stats[key]["attempts"].add(attempt.id)
                    topic_stats[key]["total"] += 1

                    user_sel = s_answers.get(str(idx))
                    corr_sel = q.get("correct_option_index")
                    if user_sel is not None and user_sel == corr_sel:
                        topic_stats[key]["correct"] += 1
            elif attempt.unit_id or attempt.topic_id:
                # Quiz-level tracking if question breakdown is unavailable
                key = (attempt.subject_id, attempt.unit_id, attempt.topic_id)
                if key not in topic_stats:
                    topic_stats[key] = {"correct": 0, "total": 0, "attempts": set()}
                topic_stats[key]["attempts"].add(attempt.id)
                tot_q = attempt.total_questions or 1
                topic_stats[key]["total"] += tot_q
                topic_stats[key]["correct"] += int(attempt.score or 0)

        weak_list: List[WeakTopicSummary] = []
        for (subj_id, u_id, t_id), stats in topic_stats.items():
            total_eval = stats["total"]
            corr_eval = stats["correct"]
            attempts_count = len(stats["attempts"])

            # Strict evidence guard: Must have at least 2 questions/attempts
            if total_eval < 2 and attempts_count < 2:
                continue

            accuracy = (corr_eval / total_eval) * 100.0 if total_eval > 0 else 0.0

            # Only flag as weak if accuracy < 60%
            if accuracy < 60.0:
                subj = db.query(Subject).get(subj_id)
                unit_obj = db.query(SyllabusUnit).get(u_id) if u_id else None
                topic_obj = db.query(SyllabusTopic).get(t_id) if t_id else None

                reason = (
                    f"Scored {accuracy:.1f}% accuracy across {total_eval} questions "
                    f"({corr_eval}/{total_eval} correct in {attempts_count} quiz attempts). "
                    f"Meets weak-area criteria (<60% with verified repeated evidence)."
                )

                weak_list.append(
                    WeakTopicSummary(
                        subject_id=subj_id,
                        subject_code=subj.code if subj else "",
                        subject_name=subj.name if subj else "",
                        unit_id=u_id,
                        unit_title=unit_obj.title if unit_obj else None,
                        topic_id=t_id,
                        topic_title=topic_obj.title if topic_obj else None,
                        attempts_evaluated=attempts_count,
                        questions_evaluated=total_eval,
                        accuracy_percentage=round(accuracy, 1),
                        reason=reason,
                        has_sufficient_evidence=True
                    )
                )

        # Sort weakest first
        weak_list.sort(key=lambda x: x.accuracy_percentage)
        return weak_list

    # =========================================================================
    # 2. ADAPTIVE STUDY PLANNER
    # =========================================================================

    def create_study_plan(
        self,
        db: Session,
        current_user: User,
        request: StudyBuddyPlanCreateRequest
    ) -> StudyBuddyPlanResponse:
        """
        Create a practical, syllabus-grounded adaptive study plan.
        - Validates active subject, department authorization, and published syllabus.
        - Enforces realistic scheduling feasibility based on target date and daily budget.
        - Prioritizes topics with repeated low quiz scores and unpracticed topics.
        """
        # 1. Subject and department validation
        subject = db.query(Subject).filter(Subject.id == request.subject_id).first()
        if not subject:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

        if not subject.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject '{subject.code}' is inactive. Study plans can only be created for active subjects."
            )

        user_dept = _get_user_department(current_user)
        if current_user.role == UserRole.STUDENT:
            if not user_dept or _normalize_dept(user_dept) != _normalize_dept(subject.department):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Subject '{subject.code}' belongs to department '{subject.department}'."
                )

        # 2. Published Syllabus Document validation
        syllabus_doc = (
            db.query(SyllabusDocument)
            .filter(
                SyllabusDocument.subject_id == subject.id,
                SyllabusDocument.is_published == True,
                SyllabusDocument.review_status == SyllabusReviewStatus.APPROVED
            )
            .order_by(desc(SyllabusDocument.version))
            .first()
        )
        if not syllabus_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No approved, published syllabus available for subject '{subject.code}'."
            )

        # 3. Target date validation
        today = date.today()
        if request.target_date and request.target_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target date cannot be in the past. Please select today or a future date."
            )

        # 4. Units & Topics selection
        units_query = (
            db.query(SyllabusUnit)
            .filter(SyllabusUnit.document_id == syllabus_doc.id)
            .order_by(SyllabusUnit.order)
        )
        if request.unit_ids:
            units = units_query.filter(SyllabusUnit.id.in_(request.unit_ids)).all()
            if not units:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="None of the specified unit IDs exist in the active published syllabus."
                )
        else:
            units = units_query.all()

        if not units:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Syllabus version {syllabus_doc.version} has no structured units available for planning."
            )

        # 5. Build raw task candidates based on syllabus structure
        task_candidates: List[Dict[str, Any]] = []

        # Analyze past quiz performance on this subject for adaptive prioritization
        past_attempts = (
            db.query(StudyBuddyQuizAttempt)
            .filter(
                StudyBuddyQuizAttempt.student_id == current_user.id,
                StudyBuddyQuizAttempt.subject_id == subject.id,
                StudyBuddyQuizAttempt.status == QuizStatus.COMPLETED
            )
            .all()
        )
        weak_topics = self._calculate_weak_topics(db, past_attempts)
        weak_unit_ids = {w.unit_id for w in weak_topics if w.unit_id is not None}
        weak_topic_ids = {w.topic_id for w in weak_topics if w.topic_id is not None}

        # Collect units/topics already practiced in quizzes
        practiced_unit_ids = set()
        practiced_topic_ids = set()
        for a in past_attempts:
            if a.unit_id:
                practiced_unit_ids.add(a.unit_id)
            if a.topic_id:
                practiced_topic_ids.add(a.topic_id)
            for q in (a.questions_data or []):
                prov = q.get("provenance") or {}
                if prov.get("unit_id"):
                    practiced_unit_ids.add(prov["unit_id"])
                if prov.get("topic_id"):
                    practiced_topic_ids.add(prov["topic_id"])

        for unit in units:
            topics = (
                db.query(SyllabusTopic)
                .filter(SyllabusTopic.unit_id == unit.id)
                .order_by(SyllabusTopic.order)
                .all()
            )

            # Determine unit-level priority
            if unit.id in weak_unit_ids:
                unit_prio = "high"
                unit_reason = f"Prioritized high: Identified as a weak area in recent quizzes (<60% accuracy)"
            elif unit.id not in practiced_unit_ids:
                unit_prio = "medium"
                unit_reason = "Prioritized medium: Core syllabus unit not yet practiced in quizzes"
            else:
                unit_prio = "low"
                unit_reason = "Scheduled for revision: Previously practiced with satisfactory scores"

            # 1. Unit Overview / Concept study task
            task_candidates.append({
                "title": f"Review Unit {unit.unit_number}: {unit.title}",
                "description": unit.description or f"Comprehensive conceptual study of Unit {unit.unit_number}",
                "unit_id": unit.id,
                "topic_id": None,
                "syllabus_document_id": syllabus_doc.id,
                "syllabus_version": syllabus_doc.version,
                "estimated_duration_minutes": 30,
                "priority": unit_prio,
                "recommendation_reason": unit_reason,
                "task_type": "concept_study",
                "unit_order": unit.order,
                "topic_order": 0
            })

            # 2. Topic-level study tasks
            for topic in topics:
                if topic.id in weak_topic_ids:
                    t_prio = "high"
                    t_reason = f"Prioritized high: Identified as a weak topic in previous quizzes (<60% accuracy)"
                elif topic.id not in practiced_topic_ids:
                    t_prio = "medium"
                    t_reason = "Prioritized medium: Syllabus topic not yet covered in practice quizzes"
                else:
                    t_prio = "low"
                    t_reason = "Standard revision: Previously reviewed"

                task_candidates.append({
                    "title": f"Study Topic: {topic.title}",
                    "description": f"Targeted study of '{topic.title}' under Unit {unit.unit_number}",
                    "unit_id": unit.id,
                    "topic_id": topic.id,
                    "syllabus_document_id": syllabus_doc.id,
                    "syllabus_version": syllabus_doc.version,
                    "estimated_duration_minutes": 30,
                    "priority": t_prio,
                    "recommendation_reason": t_reason,
                    "task_type": "concept_study",
                    "unit_order": unit.order,
                    "topic_order": topic.order
                })

            # 3. Unit Practice Quiz task
            task_candidates.append({
                "title": f"Practice Quiz: Unit {unit.unit_number} ({unit.title})",
                "description": f"Attempt a syllabus-grounded practice quiz to test mastery of Unit {unit.unit_number}",
                "unit_id": unit.id,
                "topic_id": None,
                "syllabus_document_id": syllabus_doc.id,
                "syllabus_version": syllabus_doc.version,
                "estimated_duration_minutes": 20,
                "priority": unit_prio,
                "recommendation_reason": "Checkpoint quiz to evaluate topic retention and reinforce concepts",
                "task_type": "practice_quiz",
                "unit_order": unit.order,
                "topic_order": 999
            })

        # 6. Feasibility Calculation & Realistic Scheduling Check
        total_estimated_minutes = sum(t["estimated_duration_minutes"] for t in task_candidates)
        daily_budget = request.daily_budget_minutes

        if request.target_date:
            available_days = (request.target_date - today).days + 1
            max_available_minutes = available_days * daily_budget

            if total_estimated_minutes > max_available_minutes:
                hours_needed = round(total_estimated_minutes / 60.0, 1)
                hours_available = round(max_available_minutes / 60.0, 1)
                suggested_days = int((total_estimated_minutes + daily_budget - 1) // daily_budget)
                suggested_date = today + timedelta(days=suggested_days)
                suggested_budget = int((total_estimated_minutes + available_days - 1) // available_days)

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"The requested schedule is unrealistic. Covering the selected syllabus content requires "
                        f"approximately {total_estimated_minutes} minutes ({hours_needed} hours), but with your daily budget "
                        f"of {daily_budget} mins/day over {available_days} days, only {max_available_minutes} minutes "
                        f"({hours_available} hours) are available. "
                        f"Please extend your target date to at least {suggested_date.isoformat()} or increase your daily "
                        f"study budget to at least {suggested_budget} mins/day."
                    )
                )

        # 7. Sort task candidates:
        # High priority first (weak topics), then Medium (unpracticed), then Low (revision)
        # Secondary sort by syllabus unit and topic order
        priority_rank = {"high": 1, "medium": 2, "low": 3}
        task_candidates.sort(key=lambda t: (priority_rank.get(t["priority"], 2), t["unit_order"], t["topic_order"]))

        # 8. Assign scheduled dates based on daily budget
        current_day_offset = 0
        current_day_minutes_used = 0
        for task in task_candidates:
            dur = task["estimated_duration_minutes"]
            if current_day_minutes_used + dur > daily_budget and current_day_minutes_used > 0:
                current_day_offset += 1
                current_day_minutes_used = 0

            task["scheduled_date"] = today + timedelta(days=current_day_offset)
            current_day_minutes_used += dur

        # 9. Handle existing active plan for this subject (archive to avoid duplicate conflicts)
        existing_active = (
            db.query(StudyBuddyPlan)
            .filter(
                StudyBuddyPlan.student_id == current_user.id,
                StudyBuddyPlan.subject_id == subject.id,
                StudyBuddyPlan.status == PlanStatus.ACTIVE
            )
            .all()
        )
        for old_plan in existing_active:
            old_plan.status = PlanStatus.ARCHIVED
            old_plan.updated_at = datetime.now(timezone.utc)

        # 10. Persist new StudyBuddyPlan
        plan_title = request.title or f"Adaptive Study Plan: {subject.name} ({subject.code})"
        new_plan = StudyBuddyPlan(
            student_id=current_user.id,
            subject_id=subject.id,
            syllabus_document_id=syllabus_doc.id,
            syllabus_version=syllabus_doc.version,
            title=plan_title,
            description=f"Structured syllabus-grounded study plan covering {len(units)} unit(s) based on curriculum v{syllabus_doc.version}",
            target_date=request.target_date,
            daily_budget_minutes=request.daily_budget_minutes,
            status=PlanStatus.ACTIVE,
            total_tasks=len(task_candidates),
            completed_tasks=0
        )
        db.add(new_plan)
        db.flush()

        # 11. Persist tasks
        plan_tasks: List[StudyBuddyPlanTask] = []
        for idx, t in enumerate(task_candidates, start=1):
            pt = StudyBuddyPlanTask(
                plan_id=new_plan.id,
                order=idx,
                title=t["title"],
                description=t["description"],
                unit_id=t["unit_id"],
                topic_id=t["topic_id"],
                syllabus_document_id=t["syllabus_document_id"],
                syllabus_version=t["syllabus_version"],
                estimated_duration_minutes=t["estimated_duration_minutes"],
                scheduled_date=t["scheduled_date"],
                priority=t["priority"],
                recommendation_reason=t["recommendation_reason"],
                task_type=t["task_type"],
                is_completed=False
            )
            db.add(pt)
            plan_tasks.append(pt)

        db.commit()
        db.refresh(new_plan)

        logger.info(f"✅ Created adaptive study plan {new_plan.id} for student {current_user.id} with {len(plan_tasks)} tasks")
        return self._format_plan_response(new_plan, plan_tasks)

    def list_student_plans(
        self,
        db: Session,
        current_user: User,
        subject_id: Optional[int] = None,
        status_filter: Optional[str] = None
    ) -> List[StudyBuddyPlanResponse]:
        """
        List all study plans owned by the authenticated student.
        """
        query = db.query(StudyBuddyPlan).filter(StudyBuddyPlan.student_id == current_user.id)

        if subject_id:
            query = query.filter(StudyBuddyPlan.subject_id == subject_id)
        if status_filter:
            try:
                st = PlanStatus(status_filter.upper())
                query = query.filter(StudyBuddyPlan.status == st)
            except ValueError:
                pass

        plans = query.order_by(desc(StudyBuddyPlan.created_at)).all()
        return [self._format_plan_response(p, p.tasks) for p in plans]

    def get_plan_detail(
        self,
        db: Session,
        current_user: User,
        plan_id: int
    ) -> StudyBuddyPlanResponse:
        """
        Retrieve complete study plan and ordered tasks with syllabus provenance.
        Enforces strict student ownership.
        """
        plan = db.query(StudyBuddyPlan).filter(StudyBuddyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found")

        # Ownership enforcement
        if plan.student_id != current_user.id:
            # Allow staff of same department to view, but forbid other students
            user_dept = _get_user_department(current_user)
            is_staff = current_user.role in [UserRole.ADMIN, UserRole.HOD, UserRole.LECTURER]
            if not is_staff or (_normalize_dept(user_dept) != _normalize_dept(plan.subject.department) and current_user.role != UserRole.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You can only access your own study plans."
                )

        return self._format_plan_response(plan, plan.tasks)

    def update_plan(
        self,
        db: Session,
        current_user: User,
        plan_id: int,
        request: StudyBuddyPlanUpdateRequest
    ) -> StudyBuddyPlanResponse:
        """
        Update permitted study plan settings (target_date, daily_budget, title, status).
        Enforces ownership and feasibility.
        """
        plan = db.query(StudyBuddyPlan).filter(StudyBuddyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found")

        if plan.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only modify your own study plans."
            )

        if request.title is not None:
            plan.title = request.title

        if request.status is not None:
            try:
                plan.status = PlanStatus(request.status.upper())
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid plan status '{request.status}'")

        # If target date or daily budget updated, check feasibility for remaining incomplete tasks
        new_target_date = request.target_date if request.target_date is not None else plan.target_date
        new_budget = request.daily_budget_minutes if request.daily_budget_minutes is not None else plan.daily_budget_minutes

        if request.target_date is not None or request.daily_budget_minutes is not None:
            today = date.today()
            if new_target_date and new_target_date < today:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target date cannot be in the past.")

            # Remaining minutes
            remaining_tasks = [t for t in plan.tasks if not t.is_completed]
            remaining_minutes = sum(t.estimated_duration_minutes for t in remaining_tasks)

            if new_target_date:
                avail_days = (new_target_date - today).days + 1
                max_avail = avail_days * new_budget
                if remaining_minutes > max_avail:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"The updated schedule is unrealistic. Remaining tasks require {remaining_minutes} minutes, "
                            f"but with {new_budget} mins/day over {avail_days} days, only {max_avail} minutes are available. "
                            f"Please extend target date or increase budget."
                        )
                    )

            plan.target_date = new_target_date
            plan.daily_budget_minutes = new_budget

        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plan)
        return self._format_plan_response(plan, plan.tasks)

    def update_task_status(
        self,
        db: Session,
        current_user: User,
        plan_id: int,
        task_id: int,
        is_completed: bool
    ) -> StudyBuddyPlanTaskResponse:
        """
        Complete or reopen an individual study plan task.
        Updates plan-level completed task counts and status automatically.
        """
        plan = db.query(StudyBuddyPlan).filter(StudyBuddyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found")

        if plan.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only modify tasks in your own study plans."
            )

        task = (
            db.query(StudyBuddyPlanTask)
            .filter(StudyBuddyPlanTask.id == task_id, StudyBuddyPlanTask.plan_id == plan_id)
            .first()
        )
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found in this study plan")

        task.is_completed = is_completed
        if is_completed:
            task.completed_at = datetime.now(timezone.utc)
        else:
            task.completed_at = None

        task.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Update plan's completed task count
        comp_count = (
            db.query(func.count(StudyBuddyPlanTask.id))
            .filter(StudyBuddyPlanTask.plan_id == plan.id, StudyBuddyPlanTask.is_completed == True)
            .scalar() or 0
        )
        plan.completed_tasks = comp_count

        if plan.completed_tasks >= plan.total_tasks and plan.total_tasks > 0:
            plan.status = PlanStatus.COMPLETED
        elif plan.status == PlanStatus.COMPLETED and not is_completed:
            plan.status = PlanStatus.ACTIVE

        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(task)

        return self._format_task_response(task)

    def regenerate_plan(
        self,
        db: Session,
        current_user: User,
        plan_id: int
    ) -> StudyBuddyPlanResponse:
        """
        Regenerate tasks based on updated quiz history while preserving completed task records.
        """
        plan = db.query(StudyBuddyPlan).filter(StudyBuddyPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study plan not found")

        if plan.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only regenerate your own study plans."
            )

        # Re-evaluate weak topics for subject
        past_attempts = (
            db.query(StudyBuddyQuizAttempt)
            .filter(
                StudyBuddyQuizAttempt.student_id == current_user.id,
                StudyBuddyQuizAttempt.subject_id == plan.subject_id,
                StudyBuddyQuizAttempt.status == QuizStatus.COMPLETED
            )
            .all()
        )
        weak_topics = self._calculate_weak_topics(db, past_attempts)
        weak_unit_ids = {w.unit_id for w in weak_topics if w.unit_id is not None}
        weak_topic_ids = {w.topic_id for w in weak_topics if w.topic_id is not None}

        # Update remaining incomplete tasks with new priority and reasons
        for task in plan.tasks:
            if not task.is_completed:
                if task.topic_id and task.topic_id in weak_topic_ids:
                    task.priority = "high"
                    task.recommendation_reason = "Prioritized high: Identified as a weak topic in updated quiz attempts"
                elif task.unit_id and task.unit_id in weak_unit_ids:
                    task.priority = "high"
                    task.recommendation_reason = "Prioritized high: Identified as a weak unit in updated quiz attempts"
                task.updated_at = datetime.now(timezone.utc)

        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plan)

        return self._format_plan_response(plan, plan.tasks)

    # =========================================================================
    # 3. HELPER FORMATTERS
    # =========================================================================

    def _format_task_response(self, task: StudyBuddyPlanTask) -> StudyBuddyPlanTaskResponse:
        """Format database task record to Pydantic schema."""
        unit_title = task.unit.title if task.unit else None
        topic_title = task.topic.title if task.topic else None

        return StudyBuddyPlanTaskResponse(
            id=task.id,
            plan_id=task.plan_id,
            order=task.order,
            title=task.title,
            description=task.description,
            unit_id=task.unit_id,
            unit_title=unit_title,
            topic_id=task.topic_id,
            topic_title=topic_title,
            syllabus_document_id=task.syllabus_document_id,
            syllabus_version=task.syllabus_version,
            estimated_duration_minutes=task.estimated_duration_minutes,
            scheduled_date=task.scheduled_date,
            priority=task.priority,
            recommendation_reason=task.recommendation_reason,
            task_type=task.task_type,
            is_completed=task.is_completed,
            completed_at=task.completed_at
        )

    def _format_plan_response(
        self,
        plan: StudyBuddyPlan,
        tasks: List[StudyBuddyPlanTask]
    ) -> StudyBuddyPlanResponse:
        """Format database plan record with tasks to Pydantic schema."""
        prog_pct = 0.0
        if plan.total_tasks > 0:
            prog_pct = round((plan.completed_tasks / plan.total_tasks) * 100.0, 1)

        task_responses = [self._format_task_response(t) for t in sorted(tasks, key=lambda x: x.order)]

        return StudyBuddyPlanResponse(
            id=plan.id,
            student_id=plan.student_id,
            subject_id=plan.subject_id,
            subject_code=plan.subject.code if plan.subject else "",
            subject_name=plan.subject.name if plan.subject else "",
            syllabus_document_id=plan.syllabus_document_id,
            syllabus_version=plan.syllabus_version,
            title=plan.title,
            description=plan.description,
            target_date=plan.target_date,
            daily_budget_minutes=plan.daily_budget_minutes,
            status=plan.status.value,
            total_tasks=plan.total_tasks,
            completed_tasks=plan.completed_tasks,
            progress_percentage=prog_pct,
            tasks=task_responses,
            created_at=plan.created_at,
            updated_at=plan.updated_at
        )


study_buddy_progress_service = StudyBuddyProgressService()
