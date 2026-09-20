// --- mode switching -------------------------------------------------

const modeButtons = document.querySelectorAll('.mode-btn');
const panels = {
  interview: document.getElementById('panel-interview'),
  resume: document.getElementById('panel-resume'),
  tracker: document.getElementById('panel-tracker'),
};

modeButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    modeButtons.forEach((b) => b.classList.remove('is-active'));
    btn.classList.add('is-active');
    const mode = btn.dataset.mode;
    Object.entries(panels).forEach(([key, panel]) => {
      panel.hidden = key !== mode;
    });
    if (mode === 'tracker') loadTrackerBoard();
  });
});

// --- loading overlay --------------------------------------------------

const overlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');

function showLoading(text) {
  loadingText.textContent = text;
  overlay.hidden = false;
}

function hideLoading() {
  overlay.hidden = true;
}

// --- shared fetch helper ----------------------------------------------

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

function renderError(container, message) {
  container.hidden = false;
  container.innerHTML = `<div class="result-error">${escapeHtml(message)}</div>`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// --- interview questions ------------------------------------------------

const interviewForm = document.getElementById('interview-form');
const interviewResults = document.getElementById('interview-results');

interviewForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    role: document.getElementById('int-role').value.trim(),
    company: document.getElementById('int-company').value.trim(),
    job_description: document.getElementById('int-jd').value.trim(),
  };
  showLoading('Generating interview questions\u2026');
  try {
    const data = await postJSON('/api/interview-questions', payload);
    renderInterviewResults(interviewResults, data.result);
    prependRecent(data.id, 'interview', payload.role, payload.company);
  } catch (err) {
    renderError(interviewResults, err.message);
  } finally {
    hideLoading();
  }
});

function renderInterviewResults(container, result) {
  container.hidden = false;
  const section = (title, note, items) => `
    <div class="q-section">
      <h2>${escapeHtml(title)}</h2>
      <p class="q-section-note">${escapeHtml(note)}</p>
      <ul class="q-list">${items}</ul>
    </div>`;

  const general = (result.general_questions || [])
    .map((q) => `<li>${escapeHtml(q)}</li>`).join('');
  const companySpecific = (result.company_specific_questions || [])
    .map((q) => `<li>${escapeHtml(q)}</li>`).join('');
  const scenarios = (result.scenario_questions || [])
    .map((s) => `<li>${escapeHtml(s.question)}<span class="q-scenario-note">${escapeHtml(s.what_it_tests || '')}</span></li>`)
    .join('');

  container.innerHTML =
    section('General questions', 'Commonly asked for this role, across companies.', general) +
    section('Company-style questions', "Representative of this company's known interview style.", companySpecific) +
    section('Scenario-based questions', 'Grounded in the actual responsibilities in the job description.', scenarios);
}

// --- resume builder ----------------------------------------------------

const resumeForm = document.getElementById('resume-form');
const resumeResults = document.getElementById('resume-results');

// --- resume file upload --------------------------------------------------

const resumeUpload = document.getElementById('res-upload');
const uploadStatus = document.getElementById('upload-status');
const backgroundField = document.getElementById('res-background');

resumeUpload.addEventListener('change', async () => {
  const file = resumeUpload.files[0];
  if (!file) return;
  uploadStatus.textContent = `Reading ${file.name}\u2026`;
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await fetch('/api/extract-resume', { method: 'POST', body: formData });
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Could not read that file.');
    backgroundField.value = data.text;
    uploadStatus.textContent = `Extracted from ${file.name} \u2014 review or edit above before generating.`;
  } catch (err) {
    uploadStatus.textContent = err.message;
  }
});

resumeForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    role: document.getElementById('res-role').value.trim(),
    company: document.getElementById('res-company').value.trim(),
    job_description: document.getElementById('res-jd').value.trim(),
    background: document.getElementById('res-background').value.trim(),
  };
  showLoading('Writing your resume\u2026');
  try {
    const data = await postJSON('/api/resume', payload);
    renderResumeResult(resumeResults, data.id, data.result.resume_text, payload.role);
    prependRecent(data.id, 'resume', payload.role, payload.company);
  } catch (err) {
    renderError(resumeResults, err.message);
  } finally {
    hideLoading();
  }
});

function renderResumeResult(container, entryId, text, role) {
  container.hidden = false;
  container.innerHTML = `
    <div class="resume-actions">
      <button type="button" class="secondary-btn" id="copy-resume-btn">Copy text</button>
      <button type="button" class="secondary-btn" id="download-resume-btn">Download .txt</button>
      <button type="button" class="secondary-btn" id="download-docx-btn">Download .docx</button>
    </div>
    <div class="resume-sheet">${escapeHtml(text)}</div>
    <div class="job-match-block">
      <h2>Find matching jobs</h2>
      <p class="q-section-note">Searches live postings using this resume's role and skills.</p>
      <div class="job-match-controls">
        <input type="text" id="jm-location" placeholder="City (optional)">
        <select id="jm-country" aria-label="Country">
          <option value="in">India</option>
          <option value="gb">UK</option>
          <option value="us">US</option>
          <option value="au">Australia</option>
          <option value="ca">Canada</option>
          <option value="nz">New Zealand</option>
          <option value="sg">Singapore</option>
          <option value="de">Germany</option>
          <option value="fr">France</option>
          <option value="za">South Africa</option>
        </select>
        <label><input type="checkbox" class="jm-mode" value="remote" checked> Remote</label>
        <label><input type="checkbox" class="jm-mode" value="hybrid" checked> Hybrid</label>
        <label><input type="checkbox" class="jm-mode" value="onsite" checked> On-site</label>
        <button type="button" class="secondary-btn" id="jm-search-btn">Search jobs</button>
      </div>
      <div id="jm-results"></div>
    </div>`;

  document.getElementById('copy-resume-btn').addEventListener('click', () => {
    navigator.clipboard.writeText(text);
  });
  document.getElementById('download-resume-btn').addEventListener('click', () => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'resume.txt';
    a.click();
    URL.revokeObjectURL(url);
  });
  document.getElementById('download-docx-btn').addEventListener('click', () => {
    window.location.href = `/api/document/${entryId}/docx`;
  });

  document.getElementById('jm-search-btn').addEventListener('click', async () => {
    const workModes = Array.from(document.querySelectorAll('.jm-mode:checked')).map((el) => el.value);
    const jmResults = document.getElementById('jm-results');
    showLoading('Searching for matching jobs\u2026');
    try {
      const data = await postJSON('/api/job-matches', {
        role,
        resume_text: text,
        location: document.getElementById('jm-location').value.trim(),
        country: document.getElementById('jm-country').value,
        work_modes: workModes.length ? workModes : ['remote', 'hybrid', 'onsite'],
      });
      renderJobMatches(jmResults, data);
    } catch (err) {
      renderError(jmResults, err.message);
    } finally {
      hideLoading();
    }
  });
}

function renderJobMatches(container, data) {
  container.hidden = false;
  const modeLabel = { remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' };

  let salaryHtml;
  if (data.salary_estimate) {
    const s = data.salary_estimate;
    salaryHtml = `<div class="salary-estimate">
      <strong>Estimated salary range:</strong> ${s.low.toLocaleString()} \u2013 ${s.high.toLocaleString()}
      (avg. ${s.average.toLocaleString()}) &mdash; based on ${s.based_on} of ${s.out_of} matched postings that listed a salary.
      ${s.any_predicted ? '<br><span class="q-section-note">Some of these are Adzuna-estimated, not employer-disclosed.</span>' : ''}
    </div>`;
  } else {
    salaryHtml = `<div class="salary-estimate">Not enough matched postings disclosed a salary to estimate a range.</div>`;
  }

  const jobsHtml = data.jobs.length
    ? data.jobs.map((j, i) => `
      <div class="job-card">
        <div class="job-card-top">
          <span class="job-title">${escapeHtml(j.title)}</span>
          <span class="work-mode-tag work-mode-${j.work_mode}">${modeLabel[j.work_mode] || j.work_mode}</span>
        </div>
        <div class="job-meta">${escapeHtml(j.company)} &mdash; ${escapeHtml(j.location)}</div>
        ${j.salary_min ? `<div class="job-salary">${j.salary_min.toLocaleString()} \u2013 ${j.salary_max.toLocaleString()}</div>` : ''}
        <div class="job-card-actions">
          <a href="${j.url}" target="_blank" rel="noopener noreferrer" class="job-link">View posting \u2197</a>
          <button type="button" class="track-btn" data-job-index="${i}">+ Track this job</button>
        </div>
      </div>`).join('')
    : '<p class="q-section-note">No matching postings found. Try a different location or country.</p>';

  container.innerHTML = `
    <p class="q-section-note">Searched for: &ldquo;${escapeHtml(data.search_query)}&rdquo;</p>
    ${salaryHtml}
    <div class="job-list">${jobsHtml}</div>`;

  container.querySelectorAll('.track-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const job = data.jobs[Number(btn.dataset.jobIndex)];
      btn.disabled = true;
      btn.textContent = 'Adding\u2026';
      try {
        await postJSON('/api/tracker', {
          title: job.title,
          company: job.company,
          location: job.location,
          url: job.url,
          salary_min: job.salary_min,
          salary_max: job.salary_max,
          work_mode: job.work_mode,
        });
        btn.textContent = '\u2713 Tracked';
      } catch (err) {
        btn.disabled = false;
        btn.textContent = '+ Track this job';
        alert(err.message);
      }
    });
  });
}

// --- cover letter (shares the resume form's fields) ----------------------

const coverLetterBtn = document.getElementById('cover-letter-btn');
const coverLetterResults = document.getElementById('cover-letter-results');

coverLetterBtn.addEventListener('click', async () => {
  const payload = {
    role: document.getElementById('res-role').value.trim(),
    company: document.getElementById('res-company').value.trim(),
    job_description: document.getElementById('res-jd').value.trim(),
    background: document.getElementById('res-background').value.trim(),
  };
  if (!payload.role || !payload.company || !payload.job_description || !payload.background) {
    coverLetterResults.hidden = false;
    coverLetterResults.innerHTML = '<div class="result-error">Fill in role, company, job description, and background first.</div>';
    return;
  }
  showLoading('Writing your cover letter\u2026');
  try {
    const data = await postJSON('/api/cover-letter', payload);
    renderCoverLetterResult(coverLetterResults, data.id, data.result.letter_text);
    prependRecent(data.id, 'cover_letter', payload.role, payload.company);
  } catch (err) {
    renderError(coverLetterResults, err.message);
  } finally {
    hideLoading();
  }
});

function renderCoverLetterResult(container, entryId, text) {
  container.hidden = false;
  container.innerHTML = `
    <div class="resume-actions">
      <button type="button" class="secondary-btn" id="copy-letter-btn">Copy text</button>
      <button type="button" class="secondary-btn" id="download-letter-btn">Download .txt</button>
      <button type="button" class="secondary-btn" id="download-letter-docx-btn">Download .docx</button>
    </div>
    <div class="resume-sheet">${escapeHtml(text)}</div>`;

  document.getElementById('copy-letter-btn').addEventListener('click', () => {
    navigator.clipboard.writeText(text);
  });
  document.getElementById('download-letter-btn').addEventListener('click', () => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cover-letter.txt';
    a.click();
    URL.revokeObjectURL(url);
  });
  document.getElementById('download-letter-docx-btn').addEventListener('click', () => {
    window.location.href = `/api/document/${entryId}/docx`;
  });
}

// --- application tracker ---------------------------------------------------

const trackerBoard = document.getElementById('tracker-board');
const STATUS_LABELS = { applied: 'Applied', interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected' };
const STATUS_ORDER = ['applied', 'interviewing', 'offer', 'rejected'];

async function loadTrackerBoard() {
  trackerBoard.innerHTML = '<p class="q-section-note">Loading\u2026</p>';
  try {
    const res = await fetch('/api/tracker');
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    const data = await res.json();
    renderTrackerBoard(data.jobs);
  } catch (err) {
    trackerBoard.innerHTML = `<div class="result-error">${escapeHtml(err.message)}</div>`;
  }
}

function renderTrackerBoard(jobs) {
  if (!jobs.length) {
    trackerBoard.innerHTML = '<p class="q-section-note">Nothing tracked yet \u2014 add a job from a match search in Resume builder.</p>';
    return;
  }

  const columnsHtml = STATUS_ORDER.map((status) => {
    const columnJobs = jobs.filter((j) => j.status === status);
    const cardsHtml = columnJobs.map((j) => `
      <div class="tracker-card" data-id="${j.id}">
        <div class="tracker-card-title">${escapeHtml(j.title)}</div>
        <div class="tracker-card-meta">${escapeHtml(j.company)}${j.location ? ' \u2014 ' + escapeHtml(j.location) : ''}</div>
        ${j.salary_min ? `<div class="job-salary">${Number(j.salary_min).toLocaleString()} \u2013 ${Number(j.salary_max).toLocaleString()}</div>` : ''}
        <textarea class="tracker-notes" placeholder="Notes\u2026" data-id="${j.id}">${escapeHtml(j.notes || '')}</textarea>
        <div class="tracker-card-controls">
          <select class="tracker-status-select" data-id="${j.id}" aria-label="Status">
            ${STATUS_ORDER.map((s) => `<option value="${s}" ${s === status ? 'selected' : ''}>${STATUS_LABELS[s]}</option>`).join('')}
          </select>
          <button type="button" class="tracker-delete-btn" data-id="${j.id}" title="Remove">\u00d7</button>
        </div>
        ${j.url ? `<a href="${j.url}" target="_blank" rel="noopener noreferrer" class="job-link">View posting \u2197</a>` : ''}
      </div>`).join('');

    return `
      <div class="tracker-column">
        <h3>${STATUS_LABELS[status]} <span class="tracker-count">${columnJobs.length}</span></h3>
        <div class="tracker-cards">${cardsHtml || '<p class="tracker-empty">Empty</p>'}</div>
      </div>`;
  }).join('');

  trackerBoard.innerHTML = `<div class="tracker-columns">${columnsHtml}</div>`;

  trackerBoard.querySelectorAll('.tracker-status-select').forEach((sel) => {
    sel.addEventListener('change', async () => {
      try {
        await fetch(`/api/tracker/${sel.dataset.id}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: sel.value }),
        });
        loadTrackerBoard();
      } catch (err) {
        alert('Could not update status: ' + err.message);
      }
    });
  });

  trackerBoard.querySelectorAll('.tracker-delete-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm('Remove this job from the tracker?')) return;
      try {
        await fetch(`/api/tracker/${btn.dataset.id}`, { method: 'DELETE' });
        loadTrackerBoard();
      } catch (err) {
        alert('Could not remove: ' + err.message);
      }
    });
  });

  trackerBoard.querySelectorAll('.tracker-notes').forEach((ta) => {
    ta.addEventListener('blur', async () => {
      try {
        await fetch(`/api/tracker/${ta.dataset.id}/notes`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notes: ta.value }),
        });
      } catch (err) {
        console.error('Could not save note', err);
      }
    });
  });
}

// --- recent list ---------------------------------------------------------

const recentList = document.getElementById('recent-list');

function prependRecent(id, kind, role, company) {
  const emptyEl = recentList.querySelector('.recent-empty');
  if (emptyEl) emptyEl.remove();

  const li = document.createElement('li');
  li.innerHTML = `
    <button class="recent-item" type="button" data-id="${id}" data-kind="${kind}">
      <span class="recent-role">${escapeHtml(role)}</span>
      <span class="recent-company">${escapeHtml(company)}</span>
    </button>`;
  recentList.prepend(li);
}

recentList.addEventListener('click', async (e) => {
  const btn = e.target.closest('.recent-item');
  if (!btn) return;
  const id = btn.dataset.id;
  const kind = btn.dataset.kind;
  showLoading('Loading\u2026');
  try {
    const res = await fetch(`/api/history/${id}`);
    if (res.status === 401) {
      window.location.href = '/login';
      return;
    }
    const entry = await res.json();
    const targetMode = kind === 'interview' ? 'interview' : 'resume';
    modeButtons.forEach((b) => b.classList.toggle('is-active', b.dataset.mode === targetMode));
    Object.entries(panels).forEach(([key, panel]) => { panel.hidden = key !== targetMode; });
    if (kind === 'interview') {
      renderInterviewResults(interviewResults, entry.result);
    } else if (kind === 'cover_letter') {
      renderCoverLetterResult(coverLetterResults, entry.id, entry.result.letter_text);
    } else {
      renderResumeResult(resumeResults, entry.id, entry.result.resume_text, entry.role);
    }
  } catch (err) {
    console.error(err);
  } finally {
    hideLoading();
  }
});

// --- logout --------------------------------------------------------------

document.getElementById('logout-btn').addEventListener('click', async () => {
  await fetch('/logout', { method: 'POST' });
  window.location.href = '/login';
});
