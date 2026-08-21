-- 1. Create companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    website VARCHAR(255),
    industry VARCHAR(100),
    location VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    logo_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_companies_id ON companies(id);
CREATE INDEX IF NOT EXISTS ix_companies_name ON companies(name);

-- 2. Create job_postings table
CREATE TABLE IF NOT EXISTS job_postings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    required_skills JSONB DEFAULT '[]',
    experience_level VARCHAR(50),
    cgpa_criteria FLOAT,
    branch_eligibility JSONB DEFAULT '[]',
    location VARCHAR(255),
    salary_range VARCHAR(100),
    application_deadline TIMESTAMP WITH TIME ZONE,
    drive_date TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'open',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_job_postings_id ON job_postings(id);
CREATE INDEX IF NOT EXISTS ix_job_postings_company_id ON job_postings(company_id);
CREATE INDEX IF NOT EXISTS ix_job_postings_status ON job_postings(status);

-- 3. Create applications table
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_posting_id INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'applied',
    eligibility_score FLOAT,
    match_percentage FLOAT,
    notes TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_applications_id ON applications(id);
CREATE INDEX IF NOT EXISTS ix_applications_student_id ON applications(student_id);
CREATE INDEX IF NOT EXISTS ix_applications_job_posting_id ON applications(job_posting_id);

-- 4. Create shortlists table
CREATE TABLE IF NOT EXISTS shortlists (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    job_posting_id INTEGER NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    reason TEXT,
    shortlisted_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_shortlists_id ON shortlists(id);
CREATE INDEX IF NOT EXISTS ix_shortlists_student_id ON shortlists(student_id);
CREATE INDEX IF NOT EXISTS ix_shortlists_company_id ON shortlists(company_id);

SELECT '✅ Tables created successfully!' as status;
