import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const Landing = () => {
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  const hasRedirected = useRef(false);

  // Redirect if already logged in - ONLY ONCE
  useEffect(() => {
    if (hasRedirected.current) return;
    
    if (token && user) {
      const role = user.role?.toLowerCase();
      const roleMap = {
        'student': '/student/dashboard',
        'lecturer': '/lecturer/dashboard',
        'hod': '/hod/dashboard',
        'admin': '/admin/dashboard',
        'placement_officer': '/placement/dashboard'
      };
      const redirectPath = roleMap[role] || '/login';
      hasRedirected.current = true;
      navigate(redirectPath, { replace: true });
    }
  }, [token, user, navigate]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
          }
        });
      },
      { threshold: 0.25 }
    );

    const elements = document.querySelectorAll('.feature, .bento, .network');
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  const toggleTheme = () => {
    const current = document.documentElement.getAttribute('data-theme');
    document.documentElement.setAttribute(
      'data-theme',
      current === 'dark' ? 'light' : 'dark'
    );
  };

  useEffect(() => {
    const container = document.getElementById('particles');
    if (!container) return;

    for (let i = 0; i < 22; i++) {
      const p = document.createElement('div');
      p.className = 'particle';
      p.style.left = Math.random() * 100 + 'vw';
      p.style.bottom = '-10px';
      p.style.animationDuration = 12 + Math.random() * 14 + 's';
      p.style.animationDelay = Math.random() * 14 + 's';
      container.appendChild(p);
    }
  }, []);

  return (
    <div className="landing-wrapper">
      {/* Background Effects */}
      <div className="bg-field"></div>
      <div className="bg-grid"></div>
      <div className="grid-spotlight"></div>
      <div className="col-guides">
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span>
      </div>
      <div className="particles" id="particles"></div>

      {/* Header */}
      <div className="header-hub">
        <span className="tag active">Matrix Hub</span>
        <span className="tag">Chats</span>
        <span className="tag">Documents</span>
        <span className="tag">Profile</span>
        <div className="theme-toggle" id="themeToggle" role="button" onClick={toggleTheme}></div>
      </div>

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-stage">
          <div className="hero-ring"></div>
          <div className="hero-ring r2"></div>
          <span className="orbit-dot od1"></span>
          <span className="orbit-dot od2"></span>
          <h1>
            <span className="wordmark">
              <span className="wm-edu">Edu</span>
              <span className="wm-matrix">Matrix</span>
            </span>
          </h1>
        </div>
        <div className="hero-underline"></div>
        <div className="scroll-indicator">Start Scrolling ↓</div>
      </section>

      {/* Feature 1: Chat */}
      <section className="feature" id="f1">
        <div className="feature-inner">
          <div className="feature-copy">
            <div className="feature-index">01 — Chat With Lecturers &amp; Classmates</div>
            <h2>Ask a question, get an answer from a real person.</h2>
            <p>Message your lecturer directly about a lecture or assignment, or drop into your class group chat — all threaded by course, so nothing gets lost.</p>
            <div className="feature-tags">
              <span>Course-threaded</span>
              <span>Read receipts</span>
              <span>Office hours built in</span>
            </div>
          </div>
          <div className="feature-visual">
            <div className="panel chat-panel">
              <div className="panel-label">
                <span><span className="status-dot"></span>Philosophy 204 · Prof. Rao</span>
              </div>
              <div className="chat-thread">
                <div className="bubble-row user">
                  <div className="bubble user b1">Could you go over the categorical imperative example again before Friday?</div>
                </div>
                <div className="read-receipt">Seen</div>
                <div className="bubble-row">
                  <div className="mini-avatar">MR</div>
                  <div className="bubble bot b2">Of course — I'll post a short recap video tonight and cover it again at office hours.</div>
                </div>
                <div className="bubble-row">
                  <div className="mini-avatar">MR</div>
                  <div className="bubble bot b3">
                    <div className="typing-dots"><span></span><span></span><span></span></div>
                  </div>
                </div>
              </div>
              <div className="chat-input">Message Prof. Rao…</div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature 2: Resume Analyzer */}
      <section className="feature reverse" id="f2">
        <div className="feature-inner">
          <div className="feature-copy">
            <div className="feature-index">02 — Resume Matrix Analyzer</div>
            <h2>See your resume the way a recruiter will.</h2>
            <p>Upload a draft and get an instant read on skills coverage, experience depth, and project strength — with comments your career-services lecturer can review too.</p>
            <div className="feature-tags">
              <span>Skills coverage</span>
              <span>Gap detection</span>
              <span>Lecturer review</span>
            </div>
          </div>
          <div className="feature-visual">
            <div className="panel">
              <div className="panel-label">Resume Scan</div>
              <div className="doc-frame">
                <div className="doc-line w1"></div>
                <div className="doc-line w2"></div>
                <div className="doc-line w3"></div>
                <div className="doc-line w4"></div>
                <div className="doc-line w3"></div>
                <div className="doc-line w5"></div>
                <div className="doc-line w4" style={{ marginBottom: 0 }}></div>
                <div className="scan-line"></div>
              </div>
              <div className="score-row">
                <div className="score-item">
                  <div className="score-num">86</div>
                  <div className="score-label">Skills</div>
                </div>
                <div className="score-item">
                  <div className="score-num">72</div>
                  <div className="score-label">Experience</div>
                </div>
                <div className="score-item">
                  <div className="score-num">91</div>
                  <div className="score-label">Projects</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature 3: Smart Schedule */}
      <section className="feature" id="f3">
        <div className="feature-inner">
          <div className="feature-copy">
            <div className="feature-index">03 — Smart Schedule</div>
            <h2>Every class and deadline, ranked by what matters now.</h2>
            <p>Assignments, readings, and lecturer feedback pulled into one list — sorted by what's actually urgent, not just what's next on the calendar.</p>
            <div className="feature-tags">
              <span>Auto-prioritized</span>
              <span>Course-linked</span>
              <span>Zero setup</span>
            </div>
          </div>
          <div className="feature-visual">
            <div className="panel">
              <div className="panel-label">Today</div>
              <div className="task-card">
                <div>
                  <div className="task-title">Ethics Draft due</div>
                  <div className="task-sub">Philosophy 204</div>
                </div>
                <div className="task-meta urgent">14:00</div>
              </div>
              <div className="task-card">
                <div>
                  <div className="task-title">Studio Critique</div>
                  <div className="task-sub">Design Lab</div>
                </div>
                <div className="task-meta">16:30</div>
              </div>
              <div className="task-card" style={{ marginBottom: 0 }}>
                <div>
                  <div className="task-title">Reading Response</div>
                  <div className="task-sub">Comparative Lit</div>
                </div>
                <div className="task-meta">Tomorrow</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature 4: Academic Insights */}
      <section className="feature reverse" id="f4">
        <div className="feature-inner">
          <div className="feature-copy">
            <div className="feature-index">04 — Academic Insights</div>
            <h2>A clear map of where you stand.</h2>
            <p>Skills, experience, projects, and academic history — plotted together so both you and your lecturer can see strengths and gaps at a glance.</p>
            <div className="feature-tags">
              <span>Live tracking</span>
              <span>Four dimensions</span>
              <span>Shared with lecturers</span>
            </div>
          </div>
          <div className="feature-visual">
            <div className="panel">
              <div className="panel-label" style={{ justifyContent: 'center' }}>Profile Radar</div>
              <div className="radar-wrap">
                <div className="radar-labels">
                  <svg viewBox="0 0 200 200" width="220" style={{ overflow: 'visible' }}>
                    <polygon points="100,20 180,100 100,180 20,100" fill="none" stroke="var(--grid-line)" strokeWidth="1" />
                    <polygon points="100,50 150,100 100,150 50,100" fill="none" stroke="var(--grid-line)" strokeWidth="1" />
                    <line x1="100" y1="20" x2="100" y2="180" stroke="var(--grid-line)" strokeWidth="1" />
                    <line x1="20" y1="100" x2="180" y2="100" stroke="var(--grid-line)" strokeWidth="1" />
                    <polygon points="100,30 165,100 100,170 45,100" fill="rgba(139,92,246,0.28)" stroke="url(#radarStroke)" strokeWidth="2" />
                    <defs>
                      <linearGradient id="radarStroke" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#06B6D4" />
                        <stop offset="100%" stopColor="#8B5CF6" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <span className="rl-1">Skills</span>
                  <span className="rl-2">Experience</span>
                  <span className="rl-3">Projects</span>
                  <span className="rl-4">Academic History</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Network Section */}
      <section className="connect-section">
        <div className="connect-heading">05 — One Network</div>
        <div className="connect-title">Everyone in your course, one live connection apart.</div>
        <div className="network" id="network">
          <svg viewBox="0 0 760 360" width="100%" style={{ overflow: 'visible' }}>
            <g stroke="var(--cyan)" strokeWidth="1.4" fill="none" opacity="0.55">
              <path id="p1" d="M380,180 L140,80" />
              <path id="p2" d="M380,180 L620,80" />
              <path id="p3" d="M380,180 L140,280" />
              <path id="p4" d="M380,180 L620,280" />
              <path id="p5" d="M380,180 L380,50" />
              <path id="p6" d="M380,180 L380,310" />
            </g>
            <g className="flow">
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="2.4s" repeatCount="indefinite"><mpath href="#p1" /></animateMotion>
              </circle>
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="2.1s" repeatCount="indefinite"><mpath href="#p2" /></animateMotion>
              </circle>
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="2.7s" repeatCount="indefinite"><mpath href="#p3" /></animateMotion>
              </circle>
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="2.3s" repeatCount="indefinite"><mpath href="#p4" /></animateMotion>
              </circle>
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="1.9s" repeatCount="indefinite"><mpath href="#p5" /></animateMotion>
              </circle>
              <circle r="3.5" fill="#F8FAFC">
                <animateMotion dur="2.5s" repeatCount="indefinite"><mpath href="#p6" /></animateMotion>
              </circle>
            </g>
            <circle cx="380" cy="180" r="30" fill="url(#coreGrad)" stroke="var(--violet)" strokeWidth="1.5" />
            <text x="380" y="184" textAnchor="middle" className="network-label" fill="var(--silver-1)" fontSize="10">YOU</text>
            <defs>
              <radialGradient id="coreGrad" cx="35%" cy="30%" r="70%">
                <stop offset="0%" stopColor="#1a1f2e" />
                <stop offset="100%" stopColor="#050608" />
              </radialGradient>
            </defs>
            <g>
              <circle cx="140" cy="80" r="22" fill="var(--bg)" stroke="var(--cyan)" strokeWidth="1.5" />
              <text x="140" y="84" textAnchor="middle" className="network-label" fontSize="9">MR</text>
              <text x="140" y="118" textAnchor="middle" className="network-label" fontSize="9">Prof. Rao</text>
              <circle cx="620" cy="80" r="22" fill="var(--bg)" stroke="var(--cyan)" strokeWidth="1.5" />
              <text x="620" y="84" textAnchor="middle" className="network-label" fontSize="9">AK</text>
              <text x="620" y="118" textAnchor="middle" className="network-label" fontSize="9">Aisha K.</text>
              <circle cx="140" cy="280" r="22" fill="var(--bg)" stroke="var(--cyan)" strokeWidth="1.5" />
              <text x="140" y="284" textAnchor="middle" className="network-label" fontSize="9">JT</text>
              <text x="140" y="318" textAnchor="middle" className="network-label" fontSize="9">Jon T.</text>
              <circle cx="620" cy="280" r="22" fill="var(--bg)" stroke="var(--cyan)" strokeWidth="1.5" />
              <text x="620" y="284" textAnchor="middle" className="network-label" fontSize="9">SG</text>
              <text x="620" y="318" textAnchor="middle" className="network-label" fontSize="9">Study Group</text>
              <circle cx="380" cy="50" r="20" fill="var(--bg)" stroke="var(--violet)" strokeWidth="1.5" />
              <text x="380" y="54" textAnchor="middle" className="network-label" fontSize="9">DL</text>
              <text x="380" y="24" textAnchor="middle" className="network-label" fontSize="9">Design Lab</text>
              <circle cx="380" cy="310" r="20" fill="var(--bg)" stroke="var(--violet)" strokeWidth="1.5" />
              <text x="380" y="314" textAnchor="middle" className="network-label" fontSize="9">CS</text>
              <text x="380" y="344" textAnchor="middle" className="network-label" fontSize="9">Career Services</text>
            </g>
          </svg>
        </div>
      </section>

      {/* Bento Grid */}
      <section className="grid-section">
        <div className="grid-section-inner">
          <div className="grid-heading">06 — At A Glance</div>
          <div className="bento" id="bento">
            <div className="bento-cell">
              <div className="bento-tag">Schedule</div>
              <div>
                <div className="bento-num">100%</div>
                <div className="bento-label">Deadlines auto-ranked by urgency, every course.</div>
              </div>
            </div>
            <div className="bento-cell">
              <div className="bento-tag">Chat</div>
              <div>
                <div className="bento-num">&lt;10m</div>
                <div className="bento-label">Typical lecturer response time during office hours.</div>
              </div>
            </div>
            <div className="bento-cell">
              <div className="bento-tag">Resume Analyzer</div>
              <div>
                <div className="bento-num">3s</div>
                <div className="bento-label">Average time to a full skills scan.</div>
              </div>
            </div>
            <div className="bento-cell">
              <div className="bento-tag">Insights</div>
              <div>
                <div className="bento-num">4</div>
                <div className="bento-label">Dimensions tracked across your profile.</div>
              </div>
            </div>
            <div className="bento-cell">
              <div className="bento-tag">Built for real classes</div>
              <div>
                <div className="bento-num">One login</div>
                <div className="bento-label">Chat, resume review, schedule, and insights — the same tools your lecturers use, in one workspace.</div>
              </div>
            </div>
            <div className="bento-cell">
              <div className="bento-tag">Private by default</div>
              <div>
                <div className="bento-num">Your data</div>
                <div className="bento-label">Messages and grades stay scoped to your course — nothing shared without you choosing to.</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta">
        <div className="cta-eyebrow">Matrix Hub // Ready When You Are</div>
        <h2>Your class, your lecturers, one workspace.</h2>
        <button className="cta-btn" onClick={() => navigate('/login')}>Enter EduMatrix</button>
        <div className="cta-note">No setup required — sign in with your school account.</div>
      </section>

      {/* Footer */}
      <footer>
        <span>EduMatrix</span>
        <span>© 2026</span>
      </footer>

      <style>{`
        :root{
          --cyan:#06B6D4;
          --violet:#8B5CF6;
          --emerald:#10B981;
          --red:#f87171;
          --amber:#fbbf24;
        }
        [data-theme="dark"]{
          --bg:#000000;
          --silver-1:#F8FAFC;
          --silver-2:#94A3B8;
          --silver-3:#64748B;
          --glass: rgba(255,255,255,0.03);
          --glass-strong: rgba(255,255,255,0.05);
          --glass-border: rgba(255,255,255,0.09);
          --grid-line: rgba(148,163,184,0.08);
          --doc-bg-1:#fdfdfd; --doc-bg-2:#eef0f2; --doc-text:#1a1a1a; --doc-line:#d7dade; --doc-line-2:#9aa0a8;
          --cta-btn-text:#000;
          --video-tile:#0c0f14;
        }
        [data-theme="light"]{
          --bg:#F7F7F5;
          --silver-1:#14151A;
          --silver-2:#4B5061;
          --silver-3:#7A7F91;
          --glass: rgba(20,21,26,0.03);
          --glass-strong: rgba(20,21,26,0.05);
          --glass-border: rgba(20,21,26,0.10);
          --grid-line: rgba(20,21,26,0.055);
          --doc-bg-1:#ffffff; --doc-bg-2:#eef0f2; --doc-text:#1a1a1a; --doc-line:#dfe2e5; --doc-line-2:#9aa0a8;
          --cta-btn-text:#fff;
          --video-tile:#e9eaec;
        }
        .landing-wrapper *{margin:0;padding:0;box-sizing:border-box;}
        .landing-wrapper{background:var(--bg); color:var(--silver-1); font-family:'Inter',sans-serif; overflow-x:hidden; transition:background 0.4s ease, color 0.4s ease; min-height:100vh;}
        .landing-wrapper ::selection{background:rgba(6,182,212,0.3); color:#fff;}
        .landing-wrapper .bg-field{position:fixed; inset:0; z-index:0; pointer-events:none; background:radial-gradient(700px 500px at 15% 20%, rgba(6,182,212,0.10), transparent 60%), radial-gradient(700px 600px at 85% 60%, rgba(139,92,246,0.10), transparent 60%), var(--bg); transition:background 0.4s ease;}
        .landing-wrapper .bg-grid{position:fixed; inset:0; z-index:0; pointer-events:none; background-image:linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px); background-size:72px 72px;}
        .landing-wrapper .grid-spotlight{position:fixed; top:-25%; left:-25%; z-index:0; pointer-events:none; width:780px; height:780px; border-radius:50%; background:radial-gradient(circle, rgba(6,182,212,0.18), rgba(139,92,246,0.09) 45%, transparent 72%); mix-blend-mode:screen; animation:spotlight-travel 26s ease-in-out infinite; will-change:transform;}
        [data-theme="light"] .landing-wrapper .grid-spotlight{background:radial-gradient(circle, rgba(6,182,212,0.24), rgba(139,92,246,0.13) 45%, transparent 72%); mix-blend-mode:multiply; opacity:0.6;}
        @keyframes spotlight-travel{0%{transform:translate(0vw, 0vh);}25%{transform:translate(80vw, 15vh);}50%{transform:translate(55vw, 85vh);}75%{transform:translate(5vw, 65vh);}100%{transform:translate(0vw, 0vh);}}
        .landing-wrapper .col-guides{position:fixed; inset:0; z-index:0; pointer-events:none; display:grid; grid-template-columns:repeat(12,1fr); max-width:1400px; margin:0 auto; left:0; right:0;}
        .landing-wrapper .col-guides span{border-left:1px solid var(--grid-line); height:100%;}
        .landing-wrapper .col-guides span:last-child{border-right:1px solid var(--grid-line);}
        .landing-wrapper .particles{position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;}
        .landing-wrapper .particle{position:absolute; width:3px; height:3px; border-radius:50%; background:var(--cyan); opacity:0.5; filter:blur(0.5px); animation:drift linear infinite;}
        @keyframes drift{0%{transform:translateY(0) translateX(0); opacity:0;}10%{opacity:0.6;}90%{opacity:0.6;}100%{transform:translateY(-100vh) translateX(30px); opacity:0;}}
        .landing-wrapper .header-hub{position:fixed; top:22px; left:50%; transform:translateX(-50%); z-index:50; display:flex; align-items:center; gap:22px; padding:10px 10px 10px 22px; border-radius:999px; background:var(--glass-strong); border:1px solid var(--glass-border); backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%); box-shadow:0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06); transition:background 0.4s ease, border 0.4s ease;}
        .landing-wrapper .header-hub .tag{font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:var(--silver-2); font-weight:500; cursor:default; transition:color 0.3s ease;}
        .landing-wrapper .header-hub .tag:hover{color:var(--silver-1);}
        .landing-wrapper .header-hub .tag.active{color:var(--cyan);}
        .landing-wrapper .theme-toggle{width:38px; height:24px; border-radius:999px; border:1px solid var(--glass-border); background:var(--glass); position:relative; cursor:pointer; flex-shrink:0; transition:background 0.3s ease;}
        .landing-wrapper .theme-toggle::after{content:''; position:absolute; top:2px; left:2px; width:18px; height:18px; border-radius:50%; background:linear-gradient(135deg, var(--cyan), var(--violet)); transition:transform 0.3s cubic-bezier(0.4,0,0.2,1);}
        [data-theme="light"] .landing-wrapper .theme-toggle::after{transform:translateX(14px);}
        .landing-wrapper .hero{position:relative; z-index:2; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; gap:22px; padding:0 24px;}
        .landing-wrapper .hero h1{font-family:'Space Grotesk', sans-serif; font-size:clamp(48px, 8.5vw, 124px); line-height:0.98; letter-spacing:-0.02em;}
        .landing-wrapper .hero-stage{position:relative; display:inline-flex; flex-direction:column; align-items:center; justify-content:center; padding:60px 90px;}
        .landing-wrapper .hero-ring{position:absolute; top:50%; left:50%; width:380px; height:380px; margin:-190px 0 0 -190px; pointer-events:none; border-radius:50%; border:1px solid var(--grid-line); animation:ring-spin 26s linear infinite;}
        .landing-wrapper .hero-ring.r2{width:460px; height:460px; margin:-230px 0 0 -230px; border-style:dashed; animation-duration:34s; animation-direction:reverse; opacity:0.7;}
        @keyframes ring-spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
        .landing-wrapper .orbit-dot{position:absolute; width:7px; height:7px; border-radius:50%; background:linear-gradient(135deg, var(--cyan), var(--violet)); box-shadow:0 0 14px 3px rgba(139,92,246,0.5); top:50%; left:50%; animation:orbit-travel 12s linear infinite;}
        .landing-wrapper .orbit-dot.od2{animation-duration:18s; animation-direction:reverse;}
        @keyframes orbit-travel{from{transform:rotate(0deg) translateX(240px) rotate(0deg);}to{transform:rotate(360deg) translateX(240px) rotate(-360deg);}}
        @media (max-width:700px){.landing-wrapper .hero-ring, .landing-wrapper .orbit-dot{display:none;} .landing-wrapper .hero-stage{padding:20px;}}
        .landing-wrapper .wordmark{position:relative; isolation:isolate; display:inline-flex; align-items:center; gap:18px;}
        .landing-wrapper .wordmark::before{content:'EduMatrix'; position:absolute; inset:0; z-index:-1; font-family:'Space Grotesk', sans-serif; font-weight:500; white-space:nowrap; background:linear-gradient(135deg, var(--cyan), var(--violet)); -webkit-background-clip:text; background-clip:text; color:transparent; filter:blur(42px); opacity:0.4; animation:glow-pulse 4.5s ease-in-out infinite;}
        @keyframes glow-pulse{0%,100%{opacity:0.32; transform:scale(1);}50%{opacity:0.55; transform:scale(1.03);}}
        .landing-wrapper .wm-edu{font-weight:300; background-size:220% 100%; -webkit-background-clip:text; background-clip:text; color:transparent; animation:shimmer 8s ease-in-out infinite;}
        [data-theme="dark"] .landing-wrapper .wm-edu{background-image:linear-gradient(110deg, #F8FAFC 15%, #64748B 45%, #F8FAFC 75%);}
        [data-theme="light"] .landing-wrapper .wm-edu{background-image:linear-gradient(110deg, #14151A 15%, #7A7F91 45%, #14151A 75%);}
        .landing-wrapper .wm-matrix{font-weight:700; background-size:220% 100%; -webkit-background-clip:text; background-clip:text; color:transparent; animation:shimmer 8s ease-in-out infinite;}
        [data-theme="dark"] .landing-wrapper .wm-matrix{background-image:linear-gradient(110deg, #F8FAFC 15%, #64748B 45%, #F8FAFC 75%);}
        [data-theme="light"] .landing-wrapper .wm-matrix{background-image:linear-gradient(110deg, #14151A 15%, #7A7F91 45%, #14151A 75%);}
        @keyframes shimmer{0%,100%{background-position:0% 50%;}50%{background-position:100% 50%;}}
        .landing-wrapper .hero-underline{width:120px; height:2px; margin:6px auto 0; background:linear-gradient(90deg, transparent, var(--cyan), var(--violet), transparent); background-size:200% 100%; animation:underline-pulse 5s ease-in-out infinite, shimmer 8s ease-in-out infinite;}
        @keyframes underline-pulse{0%,100%{width:80px; opacity:0.5;}50%{width:160px; opacity:1;}}
        .landing-wrapper .scroll-indicator{margin-top:10px; font-family:'JetBrains Mono', monospace; font-size:11px; letter-spacing:0.3em; text-transform:uppercase; color:var(--silver-2); animation:bob 2.2s ease-in-out infinite;}
        @keyframes bob{0%,100%{transform:translateY(0);opacity:0.5;}50%{transform:translateY(8px);opacity:1;}}
        .landing-wrapper .feature{position:relative; z-index:2; min-height:100vh; display:flex; align-items:center; padding:120px 8vw;}
        .landing-wrapper .feature-inner{display:grid; grid-template-columns:1fr 1fr; gap:6vw; align-items:center; width:100%; max-width:1240px; margin:0 auto;}
        .landing-wrapper .feature.reverse .feature-inner{direction:rtl;}
        .landing-wrapper .feature.reverse .feature-inner > *{direction:ltr;}
        .landing-wrapper .feature-copy{opacity:0; transform:translateY(36px); transition:opacity 0.9s cubic-bezier(0.16,1,0.3,1), transform 0.9s cubic-bezier(0.16,1,0.3,1);}
        .landing-wrapper .feature-visual{opacity:0; transform:translateY(50px) scale(0.96); transition:opacity 1s cubic-bezier(0.16,1,0.3,1) 0.12s, transform 1s cubic-bezier(0.16,1,0.3,1) 0.12s;}
        .landing-wrapper .feature.in-view .feature-copy{opacity:1; transform:translateY(0);}
        .landing-wrapper .feature.in-view .feature-visual{opacity:1; transform:translateY(0) scale(1);}
        .landing-wrapper .feature-index{font-family:'JetBrains Mono', monospace; font-size:12px; letter-spacing:0.2em; color:var(--cyan); text-transform:uppercase; margin-bottom:18px; opacity:0.85;}
        .landing-wrapper .feature-copy h2{font-family:'Space Grotesk', sans-serif; font-weight:400; font-size:clamp(30px, 3vw, 42px); line-height:1.15; letter-spacing:-0.01em; color:var(--silver-1); margin-bottom:18px;}
        .landing-wrapper .feature-copy p{font-size:15.5px; line-height:1.75; color:var(--silver-2); max-width:460px; margin-bottom:26px;}
        .landing-wrapper .feature-tags{display:flex; flex-wrap:wrap; gap:10px;}
        .landing-wrapper .feature-tags span{font-family:'JetBrains Mono', monospace; font-size:11px; letter-spacing:0.05em; padding:7px 12px; border-radius:999px; border:1px solid var(--glass-border); color:var(--silver-2); background:var(--glass);}
        .landing-wrapper .panel{background:linear-gradient(180deg, var(--glass-strong), var(--glass)); border:1px solid var(--glass-border); border-radius:20px; backdrop-filter:blur(20px) saturate(140%); -webkit-backdrop-filter:blur(20px) saturate(140%); box-shadow:0 30px 80px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.06); padding:26px; transition:background 0.4s ease, border 0.4s ease;}
        .landing-wrapper .panel-label{font-family:'JetBrains Mono', monospace; font-size:11px; letter-spacing:0.14em; text-transform:uppercase; color:var(--silver-2); margin-bottom:18px; display:flex; align-items:center; justify-content:space-between;}
        .landing-wrapper .panel-label .status-dot{width:7px;height:7px;border-radius:50%; background:var(--emerald); box-shadow:0 0 8px var(--emerald); animation:pulse-dot 1.8s ease-in-out infinite; margin-right:6px; display:inline-block;}
        @keyframes pulse-dot{0%,100%{opacity:1;}50%{opacity:0.3;}}
        .landing-wrapper .chat-thread{display:flex; flex-direction:column; gap:12px;}
        .landing-wrapper .bubble-row{display:flex; align-items:flex-end; gap:8px;}
        .landing-wrapper .bubble-row.user{justify-content:flex-end;}
        .landing-wrapper .mini-avatar{width:22px;height:22px;border-radius:50%; flex-shrink:0; font-size:9px; font-weight:600; color:#fff; display:flex; align-items:center; justify-content:center; font-family:'Space Grotesk',sans-serif; background:linear-gradient(135deg, var(--violet), var(--cyan));}
        .landing-wrapper .bubble{max-width:76%; padding:12px 15px; border-radius:14px; font-size:13.5px; line-height:1.55; opacity:0; transform:translateY(10px); animation:bubble-in 0.6s ease forwards;}
        .landing-wrapper .bubble.user{background:rgba(6,182,212,0.12); border:1px solid rgba(6,182,212,0.25); border-bottom-right-radius:4px; color:var(--silver-1);}
        .landing-wrapper .bubble.bot{background:var(--glass); border:1px solid var(--glass-border); border-bottom-left-radius:4px; color:var(--silver-2);}
        .landing-wrapper .bubble.b1{animation-delay:0.1s;} .bubble.b2{animation-delay:0.5s;} .bubble.b3{animation-delay:0.9s;}
        @keyframes bubble-in{to{opacity:1; transform:translateY(0);}}
        .landing-wrapper .typing-dots{display:flex; gap:4px; padding:4px 2px;}
        .landing-wrapper .typing-dots span{width:5px;height:5px;border-radius:50%;background:var(--silver-3); animation:typing 1.2s ease-in-out infinite;}
        .landing-wrapper .typing-dots span:nth-child(2){animation-delay:0.15s;} .typing-dots span:nth-child(3){animation-delay:0.3s;}
        @keyframes typing{0%,60%,100%{opacity:0.3; transform:translateY(0);}30%{opacity:1; transform:translateY(-3px);}}
        .landing-wrapper .chat-input{margin-top:16px; display:flex; align-items:center; gap:10px; border:1px solid var(--glass-border); border-radius:12px; padding:10px 14px; font-size:13px; color:var(--silver-3); background:var(--glass);}
        .landing-wrapper .read-receipt{font-family:'JetBrains Mono', monospace; font-size:9.5px; color:var(--silver-3); text-align:right; margin-top:-4px;}
        .landing-wrapper .doc-frame{background:linear-gradient(180deg, var(--doc-bg-1), var(--doc-bg-2)); border-radius:14px; padding:26px 24px; position:relative; overflow:hidden; color:var(--doc-text);}
        .landing-wrapper .doc-frame .doc-line{height:6px; border-radius:2px; background:var(--doc-line); margin-bottom:9px;}
        .landing-wrapper .doc-frame .doc-line.w1{width:58%; height:12px; background:var(--doc-line-2); margin-bottom:14px;}
        .landing-wrapper .doc-frame .doc-line.w2{width:36%; margin-bottom:16px;}
        .landing-wrapper .doc-frame .doc-line.w3{width:92%;} .doc-frame .doc-line.w4{width:80%;} .doc-frame .doc-line.w5{width:88%;}
        .landing-wrapper .scan-line{position:absolute; left:-5%; width:110%; height:2px; top:20%; background:linear-gradient(90deg, transparent, var(--cyan) 20%, #fff 50%, var(--cyan) 80%, transparent); box-shadow:0 0 16px 2px var(--cyan), 0 0 40px 6px rgba(6,182,212,0.5);}
        .landing-wrapper .feature.in-view .scan-line{animation:scan 2.8s ease-in-out infinite;}
        @keyframes scan{0%{top:8%; opacity:0.9;}50%{top:88%; opacity:1;}100%{top:8%; opacity:0.9;}}
        .landing-wrapper .score-row{display:flex; justify-content:space-between; align-items:center; margin-top:18px;}
        .landing-wrapper .score-item{text-align:center; flex:1;}
        .landing-wrapper .score-num{font-family:'Space Grotesk',sans-serif; font-weight:500; font-size:22px; color:var(--silver-1);}
        .landing-wrapper .score-label{font-family:'JetBrains Mono', monospace; font-size:9px; letter-spacing:0.1em; text-transform:uppercase; color:var(--silver-3); margin-top:4px;}
        .landing-wrapper .task-card{background:var(--glass); border:1px solid var(--glass-border); border-radius:14px; padding:15px 16px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;}
        .landing-wrapper .task-card .task-title{font-size:13.5px; font-weight:500; color:var(--silver-1);}
        .landing-wrapper .task-card .task-sub{font-size:11.5px; color:var(--silver-3); margin-top:3px;}
        .landing-wrapper .task-meta{font-family:'JetBrains Mono', monospace; font-size:11px; color:var(--cyan); padding:5px 10px; border-radius:8px; background:rgba(6,182,212,0.08); border:1px solid rgba(6,182,212,0.2);}
        .landing-wrapper .task-meta.urgent{color:var(--red); background:rgba(248,113,113,0.08); border-color:rgba(248,113,113,0.2);}
        .landing-wrapper .radar-wrap{display:flex; justify-content:center;}
        .landing-wrapper .radar-labels{position:relative; width:220px;}
        .landing-wrapper .radar-labels span{position:absolute; font-family:'JetBrains Mono', monospace; font-size:9.5px; letter-spacing:0.06em; color:var(--silver-3); text-transform:uppercase;}
        .landing-wrapper .rl-1{top:-14px; left:50%; transform:translateX(-50%);}
        .landing-wrapper .rl-2{top:50%; right:-56px; transform:translateY(-50%);}
        .landing-wrapper .rl-3{bottom:-14px; left:50%; transform:translateX(-50%);}
        .landing-wrapper .rl-4{top:50%; left:-70px; transform:translateY(-50%);}
        .landing-wrapper .connect-section{position:relative; z-index:2; padding:60px 8vw 100px; text-align:center;}
        .landing-wrapper .connect-heading{font-family:'JetBrains Mono', monospace; font-size:12px; letter-spacing:0.2em; color:var(--silver-3); text-transform:uppercase; margin-bottom:6px;}
        .landing-wrapper .connect-title{font-family:'Space Grotesk', sans-serif; font-weight:400; font-size:clamp(26px,3.4vw,40px); color:var(--silver-1); margin-bottom:44px;}
        .landing-wrapper .network{max-width:760px; margin:0 auto; opacity:0; transform:translateY(30px); transition:opacity 0.9s cubic-bezier(0.16,1,0.3,1), transform 0.9s cubic-bezier(0.16,1,0.3,1);}
        .landing-wrapper .network.in-view{opacity:1; transform:translateY(0);}
        .landing-wrapper .network-label{font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:0.06em; fill:var(--silver-2); text-transform:uppercase;}
        .landing-wrapper .grid-section{position:relative; z-index:2; padding:20px 8vw 140px;}
        .landing-wrapper .grid-section-inner{max-width:1240px; margin:0 auto;}
        .landing-wrapper .grid-heading{font-family:'JetBrains Mono', monospace; font-size:12px; letter-spacing:0.2em; color:var(--silver-3); text-transform:uppercase; margin-bottom:28px;}
        .landing-wrapper .bento{display:grid; grid-template-columns:repeat(4, 1fr); grid-template-rows:repeat(2, auto); gap:1px; background:var(--grid-line); border:1px solid var(--grid-line); border-radius:20px; overflow:hidden;}
        .landing-wrapper .bento-cell{background:var(--bg); padding:32px 26px; display:flex; flex-direction:column; justify-content:space-between; gap:20px; min-height:180px; opacity:0; transform:translateY(24px); transition:opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1), background 0.4s ease;}
        .landing-wrapper .bento.in-view .bento-cell{opacity:1; transform:translateY(0);}
        .landing-wrapper .bento-cell:nth-child(1){transition-delay:0.05s;} .bento-cell:nth-child(2){transition-delay:0.12s;}
        .landing-wrapper .bento-cell:nth-child(3){transition-delay:0.19s;} .bento-cell:nth-child(4){transition-delay:0.26s;}
        .landing-wrapper .bento-cell:nth-child(5){transition-delay:0.33s; grid-column:span 2;}
        .landing-wrapper .bento-cell:nth-child(6){transition-delay:0.40s; grid-column:span 2;}
        .landing-wrapper .bento-cell:hover{background:var(--glass);}
        .landing-wrapper .bento-num{font-family:'Space Grotesk', sans-serif; font-weight:500; font-size:34px; background:linear-gradient(135deg, var(--cyan), var(--violet)); -webkit-background-clip:text; background-clip:text; color:transparent;}
        .landing-wrapper .bento-label{font-size:13px; color:var(--silver-2); line-height:1.5;}
        .landing-wrapper .bento-tag{font-family:'JetBrains Mono', monospace; font-size:10px; letter-spacing:0.12em; text-transform:uppercase; color:var(--silver-3);}
        @media (max-width:860px){.landing-wrapper .bento{grid-template-columns:repeat(2,1fr);} .landing-wrapper .bento-cell:nth-child(5), .landing-wrapper .bento-cell:nth-child(6){grid-column:span 2;}}
        .landing-wrapper .cta{position:relative; z-index:2; min-height:60vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; gap:22px; padding:80px 24px; border-top:1px solid var(--grid-line);}
        .landing-wrapper .cta-eyebrow{font-family:'JetBrains Mono', monospace; font-size:11px; letter-spacing:0.24em; text-transform:uppercase; color:var(--violet);}
        .landing-wrapper .cta h2{font-family:'Space Grotesk', sans-serif; font-weight:400; font-size:clamp(32px,5vw,58px); color:var(--silver-1); letter-spacing:-0.01em;}
        .landing-wrapper .cta-btn{margin-top:12px; font-size:14px; font-weight:500; color:var(--cta-btn-text); background:linear-gradient(135deg, var(--cyan), var(--violet)); padding:14px 32px; border-radius:999px; border:none; cursor:pointer; box-shadow:0 10px 40px rgba(139,92,246,0.25); transition:transform 0.3s ease, box-shadow 0.3s ease;}
        .landing-wrapper .cta-btn:hover{transform:translateY(-2px); box-shadow:0 14px 50px rgba(139,92,246,0.35);}
        .landing-wrapper .cta-note{font-size:12px; color:var(--silver-3);}
        .landing-wrapper footer{position:relative; z-index:2; padding:30px 8vw; display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--grid-line); font-size:12px; color:var(--silver-3);}
        @media (max-width: 860px){.landing-wrapper .feature-inner{grid-template-columns:1fr;} .landing-wrapper .feature.reverse .feature-inner{direction:ltr;} .landing-wrapper .feature{padding:90px 7vw;} .landing-wrapper .header-hub .tag:not(.active){display:none;} .landing-wrapper .col-guides{display:none;}}
        @media (prefers-reduced-motion: reduce){.landing-wrapper *{animation-duration:0.001s !important; transition-duration:0.001s !important;}}
      `}</style>
    </div>
  );
};

export default Landing;