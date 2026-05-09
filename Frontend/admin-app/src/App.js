import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import './App.css';

const DEFAULT_API_BASE_URL = 'http://localhost:8006';
const DEFAULT_EVENT_API_BASE_URL = 'http://localhost:8008';

function resolveApiBaseUrl(value) {
  const configuredValue = (value || '').trim();
  if (!configuredValue || configuredValue === '.' || configuredValue === './' || configuredValue === '/') {
    return DEFAULT_API_BASE_URL;
  }
  return configuredValue.replace(/\/+$/, '');
}

const API_BASE_URL = resolveApiBaseUrl(process.env.REACT_APP_UBID_API_BASE_URL);
const EVENT_API_BASE_URL = resolveApiBaseUrl(process.env.REACT_APP_EVENT_API_BASE_URL || DEFAULT_EVENT_API_BASE_URL);

const navItems = [
  { label: 'Dashboard', icon: 'home', view: 'review' },
  { label: 'UBID Master', icon: 'grid', view: 'ubid-master' },
  { label: 'UBID Status', icon: 'trend', view: 'ubid-status' },
  { label: 'Review Queue', icon: 'check', view: 'review' },
  { label: 'Event Reviews', icon: 'flag', view: 'event-reviews' },
  { label: 'Event Master', icon: 'document', view: 'event-master' },
  { label: 'Reviewed', icon: 'archive', view: 'review' },
  { label: 'Reports', icon: 'chart', view: 'review' },
  { label: 'Analytics', icon: 'trend', view: 'review' },
  { label: 'Settings', icon: 'gear', view: 'review' },
  { label: 'Users', icon: 'user', view: 'review' },
];

function Icon({ name }) {
  return (
    <span className={`icon icon-${name}`} aria-hidden="true">
      <span />
    </span>
  );
}

function getRawRecord(review) {
  return review?.incoming_record?.raw_record || {};
}

function getNormalizedRecord(review) {
  return review?.incoming_record?.normalized_record || {};
}

function getEntityName(review) {
  const raw = getRawRecord(review);
  const normalized = getNormalizedRecord(review);
  return raw.name || normalized.name || review?.incoming_record?.normalized_name || 'Unknown entity';
}

function getSourceSystem(review) {
  const raw = getRawRecord(review);
  const normalized = getNormalizedRecord(review);
  return raw.sourceSystem || raw.source_system || raw.source || normalized.sourceSystem || normalized.source_system || normalized.source || 'Unspecified';
}

function getScore(review) {
  return Number(review?.top_similarity_score || 0);
}

function getPriority(review) {
  const score = getScore(review);
  if (score >= 0.88) return 'High';
  if (score >= 0.78) return 'Medium';
  return 'Low';
}

function getConfidenceBand(review) {
  const score = getScore(review);
  if (score >= 0.9) return '90+';
  if (score >= 0.8) return '80-90';
  if (score >= 0.7) return '70-80';
  return '<70';
}

function getCandidateRecord(candidate) {
  return candidate?.matched_record_data || {};
}

function getCandidateRawRecord(candidate) {
  return getCandidateRecord(candidate).raw_record || {};
}

function getCandidateName(candidate) {
  const matchedRecord = getCandidateRecord(candidate);
  const raw = getCandidateRawRecord(candidate);
  const metadata = candidate?.matched_metadata || {};
  return raw.name || matchedRecord.normalized_name || metadata.normalized_name || 'Matched record';
}

function getCandidateAddress(candidate) {
  const matchedRecord = getCandidateRecord(candidate);
  const raw = getCandidateRawRecord(candidate);
  const metadata = candidate?.matched_metadata || {};
  return raw.address || matchedRecord.normalized_address || metadata.normalized_address || '';
}

function getCandidateIdentifierSummary(candidate) {
  const matchedRecord = getCandidateRecord(candidate);
  const raw = getCandidateRawRecord(candidate);
  const metadata = candidate?.matched_metadata || {};
  return [
    candidate?.matched_ubid,
    raw.gstin || matchedRecord.normalized_gstin || metadata.normalized_gstin,
    raw.pan || raw.panNumber || matchedRecord.normalized_pan || metadata.normalized_pan,
    raw.pincode || matchedRecord.normalized_pincode || metadata.normalized_pincode,
  ]
    .filter(Boolean)
    .join(' | ');
}

function formatScore(score) {
  const value = Number(score || 0) * 100;
  return `${value.toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  return Number(value || 0).toFixed(digits);
}

function formatSignedNumber(value, digits = 2) {
  const number = Number(value || 0);
  return `${number > 0 ? '+' : ''}${number.toFixed(digits)}`;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function statusLabel(status) {
  return String(status || 'PENDING_REVIEW').replaceAll('_', ' ');
}

function ubidStatusTone(status) {
  if (status === 'UNDER_REVIEW') return 'amber';
  if (status === 'DORMANT') return 'amber';
  if (status === 'INACTIVE') return 'red';
  return 'green';
}

function getContributionTone(score) {
  return Number(score || 0) < 0 ? 'red' : 'green';
}

function eventStatusTone(status) {
  if (status === 'UBID_MATCHED') return 'green';
  if (status === 'REVIEW_REQUIRED' || status === 'PENDING_REVIEW') return 'amber';
  return 'red';
}

function getEventIdentity(event) {
  return event.ubid || event.gstin || event.pan || event.department_record_id || '-';
}

function getEventReviewIdentity(review) {
  return review.suggested_ubid || review.gstin || review.pan || review.department_record_id || '-';
}

function getEventCandidateName(candidate) {
  const matchedRecord = candidate?.matched_record || {};
  const metadata = candidate?.metadata || {};
  return matchedRecord.normalized_name || metadata.normalized_name || metadata.entity_name || candidate?.ubid || 'Matched UBID';
}

function getEventCandidateAddress(candidate) {
  const matchedRecord = candidate?.matched_record || {};
  const metadata = candidate?.metadata || {};
  return matchedRecord.normalized_address || metadata.normalized_address || '';
}

function getEventCandidateIdentifierSummary(candidate) {
  const matchedRecord = candidate?.matched_record || {};
  const metadata = candidate?.metadata || {};
  return [
    candidate?.ubid,
    matchedRecord.normalized_gstin || metadata.normalized_gstin,
    matchedRecord.normalized_pan || metadata.normalized_pan,
    matchedRecord.normalized_pincode || metadata.normalized_pincode,
  ]
    .filter(Boolean)
    .join(' | ');
}

function StatCard({ icon, label, value, tone }) {
  return (
    <section className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon name={icon} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </section>
  );
}

function Badge({ children, tone }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function ResolutionPanel({ review, onClose, onResolved }) {
  const [action, setAction] = useState('MATCH_EXISTING');
  const [selectedCandidateId, setSelectedCandidateId] = useState(review?.candidates?.[0]?.id || '');
  const [remarks, setRemarks] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setAction('MATCH_EXISTING');
    setSelectedCandidateId(review?.candidates?.[0]?.id || '');
    setRemarks('');
    setError('');
  }, [review]);

  if (!review) return null;

  const selectedCandidate = review.candidates?.find((candidate) => String(candidate.id) === String(selectedCandidateId));

  async function submitResolution() {
    setIsSubmitting(true);
    setError('');

    const payload =
      action === 'GENERATE_NEW_UBID'
        ? { action, remarks }
        : {
            action,
            selected_candidate_id: Number(selectedCandidateId),
            remarks,
          };

    try {
      const response = await fetch(`${API_BASE_URL}/resolve/review/${review.review_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to resolve review');
      }
      onResolved(body);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <section className="resolve-panel">
        <header className="panel-header">
          <div>
            <span className="eyebrow">Review resolution</span>
            <h2>{review.review_id}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            x
          </button>
        </header>

        <div className="record-summary">
          <div>
            <label>Incoming entity</label>
            <strong>{getEntityName(review)}</strong>
          </div>
          <div>
            <label>Data record ID</label>
            <strong>{review.data_record_id || '-'}</strong>
          </div>
          <div>
            <label>Source system</label>
            <strong>{getSourceSystem(review)}</strong>
          </div>
          <div>
            <label>Top confidence</label>
            <strong>{formatScore(review.top_similarity_score)}</strong>
          </div>
        </div>

        <div className="choice-tabs">
          <button className={action === 'MATCH_EXISTING' ? 'active' : ''} type="button" onClick={() => setAction('MATCH_EXISTING')}>
            Match existing
          </button>
          <button className={action === 'GENERATE_NEW_UBID' ? 'active' : ''} type="button" onClick={() => setAction('GENERATE_NEW_UBID')}>
            Generate new UBID
          </button>
        </div>

        {action === 'MATCH_EXISTING' ? (
          <div className="candidate-list">
            {review.candidates?.length ? (
              review.candidates.map((candidate) => (
                <label className={`candidate-option ${String(candidate.id) === String(selectedCandidateId) ? 'selected' : ''}`} key={candidate.id}>
                  <input
                    type="radio"
                    name="candidate"
                    value={candidate.id}
                    checked={String(candidate.id) === String(selectedCandidateId)}
                    onChange={(event) => setSelectedCandidateId(event.target.value)}
                  />
                  <div>
                    <div className="candidate-topline">
                      <strong>{getCandidateName(candidate)}</strong>
                      <Badge tone={candidate.similarity_score >= 0.85 ? 'green' : 'amber'}>{formatScore(candidate.similarity_score)}</Badge>
                    </div>
                    <div className="candidate-record-id">{candidate.matched_data_record_id || candidate.matched_record_id || 'Matched record'}</div>
                    {getCandidateAddress(candidate) ? <p>{getCandidateAddress(candidate)}</p> : null}
                    {getCandidateIdentifierSummary(candidate) ? <small>{getCandidateIdentifierSummary(candidate)}</small> : null}
                    <div className="candidate-match-details">
                      <span>Matched field: {candidate.matched_field || '-'}</span>
                      <span>{candidate.match_type}</span>
                    </div>
                    <p>{candidate.match_reason}</p>
                  </div>
                </label>
              ))
            ) : (
              <div className="empty-panel">No candidates are available for this review.</div>
            )}
          </div>
        ) : (
          <div className="new-ubid-box">
            <Icon name="plus" />
            <div>
              <strong>Create a fresh UBID</strong>
              <p>This review will be closed as a new business identity and mapped to the incoming data record.</p>
            </div>
          </div>
        )}

        <label className="remarks-field">
          Remarks
          <textarea value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="Add reviewer remarks" />
        </label>

        {selectedCandidate && action === 'MATCH_EXISTING' ? (
          <div className="selected-note">
            Selected match: <strong>{selectedCandidate.matched_data_record_id || selectedCandidate.matched_record_id}</strong>
          </div>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}

        <footer className="panel-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary-button"
            type="button"
            onClick={submitResolution}
            disabled={isSubmitting || (action === 'MATCH_EXISTING' && !selectedCandidateId)}
          >
            {isSubmitting ? 'Resolving...' : 'Resolve Review'}
          </button>
        </footer>
      </section>
    </div>
  );
}

function EventResolutionPanel({ review, onClose, onResolved }) {
  const [selectedCandidateId, setSelectedCandidateId] = useState(review?.candidates?.[0]?.id || '');
  const [remarks, setRemarks] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSelectedCandidateId(review?.candidates?.[0]?.id || '');
    setRemarks('');
    setError('');
  }, [review]);

  if (!review) return null;

  const selectedCandidate = review.candidates?.find((candidate) => String(candidate.id) === String(selectedCandidateId));

  async function submitResolution() {
    if (!selectedCandidate?.ubid) {
      setError('Selected candidate does not have a UBID.');
      return;
    }

    setIsSubmitting(true);
    setError('');
    try {
      const response = await fetch(`${EVENT_API_BASE_URL}/events/reviews/${review.review_id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ubid: selectedCandidate.ubid,
          remarks,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to resolve event review');
      }
      onResolved(body);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <section className="resolve-panel">
        <header className="panel-header">
          <div>
            <span className="eyebrow">Event review</span>
            <h2>{review.review_id}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            x
          </button>
        </header>

        <div className="record-summary">
          <div>
            <label>Event</label>
            <strong>{review.event_id || '-'}</strong>
          </div>
          <div>
            <label>Event type</label>
            <strong>{review.event_type || '-'}</strong>
          </div>
          <div>
            <label>Entity</label>
            <strong>{review.name || '-'}</strong>
          </div>
          <div>
            <label>Top confidence</label>
            <strong>{formatScore(review.top_similarity_score)}</strong>
          </div>
        </div>

        <div className="candidate-list">
          {review.candidates?.length ? (
            review.candidates.map((candidate) => (
              <label className={`candidate-option ${String(candidate.id) === String(selectedCandidateId) ? 'selected' : ''}`} key={candidate.id}>
                <input
                  type="radio"
                  name="event-candidate"
                  value={candidate.id}
                  checked={String(candidate.id) === String(selectedCandidateId)}
                  onChange={(event) => setSelectedCandidateId(event.target.value)}
                />
                <div>
                  <div className="candidate-topline">
                    <strong>{getEventCandidateName(candidate)}</strong>
                    <Badge tone={candidate.similarity_score >= 0.85 ? 'green' : 'amber'}>{formatScore(candidate.similarity_score)}</Badge>
                  </div>
                  <div className="candidate-record-id">{candidate.ubid || 'Matched UBID'}</div>
                  {getEventCandidateAddress(candidate) ? <p>{getEventCandidateAddress(candidate)}</p> : null}
                  {getEventCandidateIdentifierSummary(candidate) ? <small>{getEventCandidateIdentifierSummary(candidate)}</small> : null}
                  <div className="candidate-match-details">
                    <span>Matched field: {candidate.matched_field || '-'}</span>
                    <span>{candidate.match_type || '-'}</span>
                  </div>
                </div>
              </label>
            ))
          ) : (
            <div className="empty-panel">No candidates are available for this review.</div>
          )}
        </div>

        <label className="remarks-field">
          Remarks
          <textarea value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="Add reviewer remarks" />
        </label>

        {selectedCandidate ? (
          <div className="selected-note">
            Selected UBID: <strong>{selectedCandidate.ubid}</strong>
          </div>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}

        <footer className="panel-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary-button" type="button" onClick={submitResolution} disabled={isSubmitting || !selectedCandidateId}>
            {isSubmitting ? 'Resolving...' : 'Resolve Review'}
          </button>
        </footer>
      </section>
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState('review');
  const [reviews, setReviews] = useState([]);
  const [ubids, setUbids] = useState([]);
  const [ubidStats, setUbidStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventReviews, setEventReviews] = useState([]);
  const [eventStats, setEventStats] = useState(null);
  const [ubidStatuses, setUbidStatuses] = useState([]);
  const [ubidComputations, setUbidComputations] = useState([]);
  const [eventReviewUbidOptions, setEventReviewUbidOptions] = useState([]);
  const [eventReviewSelections, setEventReviewSelections] = useState({});
  const [resolvingEventReviewId, setResolvingEventReviewId] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isUbidLoading, setIsUbidLoading] = useState(false);
  const [isEventLoading, setIsEventLoading] = useState(false);
  const [isEventReviewLoading, setIsEventReviewLoading] = useState(false);
  const [isUbidStatusLoading, setIsUbidStatusLoading] = useState(false);
  const [error, setError] = useState('');
  const [ubidError, setUbidError] = useState('');
  const [eventError, setEventError] = useState('');
  const [eventReviewError, setEventReviewError] = useState('');
  const [ubidStatusError, setUbidStatusError] = useState('');
  const [expandedStatusUbid, setExpandedStatusUbid] = useState('');
  const [selectedEventReview, setSelectedEventReview] = useState(null);
  const [selectedReview, setSelectedReview] = useState(null);
  const [showAllReviews, setShowAllReviews] = useState(false);
  const [filters, setFilters] = useState({
    confidence: 'All',
    search: '',
  });
  const [ubidFilters, setUbidFilters] = useState({
    search: '',
    status: 'All',
    sourceSystem: 'All',
  });
  const [eventFilters, setEventFilters] = useState({
    search: '',
    eventType: 'All',
    sourceName: 'All',
  });
  const [eventReviewFilters, setEventReviewFilters] = useState({
    search: '',
    status: 'PENDING_REVIEW',
  });
  const [ubidStatusFilters, setUbidStatusFilters] = useState({
    search: '',
    status: 'All',
    activeOnly: true,
  });

  const loadReviews = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (!showAllReviews) {
        params.set('status', 'PENDING_REVIEW');
      }
      if (filters.search.trim()) {
        params.set('search', filters.search.trim());
      }
      if (filters.confidence !== 'All') {
        params.set('confidence', filters.confidence);
      }
      const query = params.toString();
      const response = await fetch(`${API_BASE_URL}/reviews${query ? `?${query}` : ''}`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to fetch review queue');
      }
      setReviews(body.reviews || []);
    } catch (err) {
      setError(err.message);
      setReviews([]);
    } finally {
      setIsLoading(false);
    }
  }, [filters.confidence, filters.search, showAllReviews]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  const loadUbids = useCallback(async () => {
    setIsUbidLoading(true);
    setUbidError('');
    try {
      const params = new URLSearchParams();
      if (ubidFilters.search.trim()) {
        params.set('search', ubidFilters.search.trim());
      }
      if (ubidFilters.status !== 'All') {
        params.set('status', ubidFilters.status);
      }
      if (ubidFilters.sourceSystem !== 'All') {
        params.set('source_system', ubidFilters.sourceSystem);
      }
      const query = params.toString();
      const response = await fetch(`${API_BASE_URL}/ubids${query ? `?${query}` : ''}`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to fetch UBID master');
      }
      setUbids(body.ubids || []);
      setUbidStats(body.stats || null);
    } catch (err) {
      setUbidError(err.message);
      setUbids([]);
      setUbidStats(null);
    } finally {
      setIsUbidLoading(false);
    }
  }, [ubidFilters]);

  useEffect(() => {
    if (activeView === 'ubid-master') {
      loadUbids();
    }
  }, [activeView, loadUbids]);

  const loadEvents = useCallback(async (filtersToApply = null) => {
    setIsEventLoading(true);
    setEventError('');
    try {
      const params = new URLSearchParams();
      if (filtersToApply) {
        if (filtersToApply.search.trim()) {
          params.set('search', filtersToApply.search.trim());
        }
        if (filtersToApply.eventType !== 'All') {
          params.set('event_type', filtersToApply.eventType);
        }
        if (filtersToApply.sourceName !== 'All') {
          params.set('source_name', filtersToApply.sourceName);
        }
        params.set('limit', '200');
      }
      const query = params.toString();
      const [eventsResponse, statsResponse] = await Promise.all([
        fetch(`${EVENT_API_BASE_URL}/events${query ? `?${query}` : ''}`),
        fetch(`${EVENT_API_BASE_URL}/events/stats`),
      ]);
      const eventsBody = await eventsResponse.json().catch(() => ({}));
      const statsBody = await statsResponse.json().catch(() => ({}));
      if (!eventsResponse.ok) {
        throw new Error(eventsBody.detail || 'Unable to fetch event master');
      }
      if (!statsResponse.ok) {
        throw new Error(statsBody.detail || 'Unable to fetch event stats');
      }
      setEvents(eventsBody.events || []);
      setEventStats(statsBody || null);
    } catch (err) {
      setEventError(err.message);
      setEvents([]);
      setEventStats(null);
    } finally {
      setIsEventLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeView === 'event-master') {
      loadEvents();
    }
  }, [activeView, loadEvents]);

  const loadEventReviews = useCallback(async (filtersToApply = null) => {
    setIsEventReviewLoading(true);
    setEventReviewError('');
    try {
      const params = new URLSearchParams();
      if (filtersToApply) {
        if (filtersToApply.search.trim()) {
          params.set('search', filtersToApply.search.trim());
        }
        if (filtersToApply.status !== 'All') {
          params.set('status', filtersToApply.status);
        }
        params.set('limit', '200');
      }
      const query = params.toString();
      const [reviewsResponse, statsResponse] = await Promise.all([
        fetch(`${EVENT_API_BASE_URL}/events/reviews${query ? `?${query}` : ''}`),
        fetch(`${EVENT_API_BASE_URL}/events/stats`),
      ]);
      const reviewsBody = await reviewsResponse.json().catch(() => ({}));
      const statsBody = await statsResponse.json().catch(() => ({}));
      if (!reviewsResponse.ok) {
        throw new Error(reviewsBody.detail || 'Unable to fetch event reviews');
      }
      if (!statsResponse.ok) {
        throw new Error(statsBody.detail || 'Unable to fetch event stats');
      }
      setEventReviews(reviewsBody.reviews || []);
      setEventReviewSelections((current) => {
        const next = { ...current };
        (reviewsBody.reviews || []).forEach((review) => {
          if (!next[review.review_id] && review.suggested_ubid) {
            next[review.review_id] = review.suggested_ubid;
          }
        });
        return next;
      });
      setEventStats(statsBody || null);
    } catch (err) {
      setEventReviewError(err.message);
      setEventReviews([]);
      setEventStats(null);
    } finally {
      setIsEventReviewLoading(false);
    }
  }, []);

  const loadEventReviewUbidOptions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/ubids`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to fetch UBID options');
      }
      setEventReviewUbidOptions(body.ubids || []);
    } catch (err) {
      setEventReviewError(err.message);
      setEventReviewUbidOptions([]);
    }
  }, []);

  useEffect(() => {
    if (activeView === 'event-reviews') {
      loadEventReviews();
      loadEventReviewUbidOptions();
    }
  }, [activeView, loadEventReviews, loadEventReviewUbidOptions]);

  const loadUbidStatuses = useCallback(async (filtersToApply = null) => {
    setIsUbidStatusLoading(true);
    setUbidStatusError('');
    try {
      const statusParams = new URLSearchParams();
      const computationParams = new URLSearchParams();
      if (filtersToApply) {
        if (filtersToApply.search.trim()) {
          statusParams.set('ubid', filtersToApply.search.trim());
          computationParams.set('ubid', filtersToApply.search.trim());
        }
        if (!filtersToApply.activeOnly) {
          statusParams.set('active_only', 'false');
        }
        statusParams.set('limit', '200');
        computationParams.set('limit', '500');
      }
      const statusQuery = statusParams.toString();
      const computationQuery = computationParams.toString();
      const [statusResponse, computationResponse] = await Promise.all([
        fetch(`${EVENT_API_BASE_URL}/ubid-status${statusQuery ? `?${statusQuery}` : ''}`),
        fetch(`${EVENT_API_BASE_URL}/events/computations${computationQuery ? `?${computationQuery}` : ''}`),
      ]);
      const statusBody = await statusResponse.json().catch(() => ({}));
      const computationBody = await computationResponse.json().catch(() => ({}));
      if (!statusResponse.ok) {
        throw new Error(statusBody.detail || 'Unable to fetch UBID status');
      }
      if (!computationResponse.ok) {
        throw new Error(computationBody.detail || 'Unable to fetch UBID event computations');
      }
      setUbidStatuses(statusBody.statuses || []);
      setUbidComputations(computationBody.computations || []);
    } catch (err) {
      setUbidStatusError(err.message);
      setUbidStatuses([]);
      setUbidComputations([]);
    } finally {
      setIsUbidStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeView === 'ubid-status') {
      loadUbidStatuses();
    }
  }, [activeView, loadUbidStatuses]);

  const stats = useMemo(() => {
    const pending = reviews.filter((review) => review.status === 'PENDING_REVIEW').length;
    const high = reviews.filter((review) => getPriority(review) === 'High').length;
    const reviewed = reviews.filter((review) => review.status !== 'PENDING_REVIEW').length;
    const approved = reviews.filter((review) => review.status === 'RESOLVED_MATCHED').length;
    const rejected = reviews.filter((review) => review.status === 'RESOLVED_NEW_UBID').length;
    return { pending, high, reviewed, approved, rejected };
  }, [reviews]);

  const filteredReviews = useMemo(() => {
    const search = filters.search.trim().toLowerCase();
    return reviews.filter((review) => {
      const confidenceMatch = filters.confidence === 'All' || getConfidenceBand(review) === filters.confidence;
      const searchable = [
        review.review_id,
        review.suggested_ubid,
        review.data_record_id,
        getEntityName(review),
        getRawRecord(review).pan,
        getRawRecord(review).gstin,
        review.incoming_record?.normalized_pan,
        review.incoming_record?.normalized_gstin,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      const searchMatch = !search || searchable.includes(search);
      return confidenceMatch && searchMatch;
    });
  }, [reviews, filters]);

  const ubidSourceOptions = useMemo(() => {
    return [...new Set(ubids.flatMap((ubid) => ubid.source_systems || []).filter(Boolean))].sort();
  }, [ubids]);

  const effectiveUbidStats = useMemo(() => {
    if (ubidStats) return ubidStats;
    return {
      total_ubids: ubids.length,
      active_ubids: ubids.filter((ubid) => ubid.status === 'ACTIVE').length,
      inactive_ubids: ubids.filter((ubid) => ubid.status === 'INACTIVE').length,
      under_review: ubids.filter((ubid) => ubid.status === 'UNDER_REVIEW').length,
      created_today: 0,
    };
  }, [ubidStats, ubids]);

  const eventTypeOptions = useMemo(() => {
    return [...new Set(events.map((event) => event.event_type).filter(Boolean))].sort();
  }, [events]);

  const eventSourceOptions = useMemo(() => {
    return [...new Set(events.map((event) => event.source_name).filter(Boolean))].sort();
  }, [events]);

  const effectiveEventStats = useMemo(() => {
    return {
      total_events: eventStats?.total_events || events.length,
      processed_today: eventStats?.processed_today || 0,
      event_type_count: eventStats?.event_type_count || eventTypeOptions.length,
      ubid_count: eventStats?.ubid_count || 0,
      pending_reviews: eventReviews.filter((review) => review.status === 'PENDING_REVIEW').length,
    };
  }, [eventStats, events.length, eventTypeOptions.length, eventReviews]);

  const filteredUbidStatuses = useMemo(() => {
    const search = ubidStatusFilters.search.trim().toLowerCase();
    return ubidStatuses.filter((row) => {
      const searchMatch = !search || String(row.ubid || '').toLowerCase().includes(search);
      const statusMatch = ubidStatusFilters.status === 'All' || row.status === ubidStatusFilters.status;
      return searchMatch && statusMatch;
    });
  }, [ubidStatuses, ubidStatusFilters]);

  const ubidStatusStats = useMemo(() => {
    return {
      total: ubidStatuses.length,
      active: ubidStatuses.filter((row) => row.status === 'ACTIVE').length,
      dormant: ubidStatuses.filter((row) => row.status === 'DORMANT').length,
      inactive: ubidStatuses.filter((row) => row.status === 'INACTIVE').length,
      categories: ubidComputations.length,
    };
  }, [ubidStatuses, ubidComputations]);

  const computationsByUbid = useMemo(() => {
    return ubidComputations.reduce((accumulator, computation) => {
      const key = computation.ubid || 'UNKNOWN';
      accumulator[key] = accumulator[key] || [];
      accumulator[key].push(computation);
      return accumulator;
    }, {});
  }, [ubidComputations]);

  function resetFilters() {
    setShowAllReviews(true);
    setFilters({
      confidence: 'All',
      search: '',
    });
  }

  function handleResolved() {
    setSelectedReview(null);
    loadReviews();
  }

  function handleEventReviewResolved() {
    setSelectedEventReview(null);
    loadEventReviews(eventReviewFilters);
  }

  function resetUbidFilters() {
    setUbidFilters({
      search: '',
      status: 'All',
      sourceSystem: 'All',
    });
  }

  function resetEventFilters() {
    setEventFilters({
      search: '',
      eventType: 'All',
      sourceName: 'All',
    });
  }

  function resetEventReviewFilters() {
    setEventReviewFilters({
      search: '',
      status: 'PENDING_REVIEW',
    });
  }

  async function resolveEventReview(review) {
    const selectedUbid = eventReviewSelections[review.review_id] || review.suggested_ubid || '';
    if (!selectedUbid) {
      setEventReviewError('Select a UBID before resolving the event review.');
      return;
    }

    setResolvingEventReviewId(review.review_id);
    setEventReviewError('');
    try {
      const response = await fetch(`${EVENT_API_BASE_URL}/events/reviews/${review.review_id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ubid: selectedUbid,
          remarks: `Mapped from admin event review ${review.review_id}`,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || 'Unable to resolve event review');
      }
      await loadEventReviews(eventReviewFilters);
    } catch (err) {
      setEventReviewError(err.message);
    } finally {
      setResolvingEventReviewId('');
    }
  }

  function resetUbidStatusFilters() {
    setUbidStatusFilters({
      search: '',
      status: 'All',
      activeOnly: true,
    });
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="brand">
          <Icon name="shield" />
          <span>UBID Platform</span>
        </div>
        <nav>
          {navItems.map((item) => (
            <button
              className={
                (activeView === 'review' && item.label === 'Review Queue') ||
                (activeView === 'ubid-master' && item.label === 'UBID Master') ||
                (activeView === 'ubid-status' && item.label === 'UBID Status') ||
                (activeView === 'event-reviews' && item.label === 'Event Reviews') ||
                (activeView === 'event-master' && item.label === 'Event Master')
                  ? 'active'
                  : ''
              }
              key={item.label}
              type="button"
              onClick={() => setActiveView(item.view)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="admin-user">
          <Icon name="user" />
          <span>Admin User</span>
          <Icon name="chevron" />
        </div>
      </aside>

      <main className="dashboard">
        {activeView === 'ubid-master' ? (
          <>
            <header className="topbar">
              <div>
                <h1>UBID Master Dashboard</h1>
                <p>Browse consolidated UBIDs and the department records mapped to them.</p>
              </div>
              <div className="top-actions">
                <button className="secondary-button" type="button" onClick={loadUbids}>
                  <Icon name="refresh" />
                  Refresh
                </button>
                <button className="primary-button" type="button">
                  <Icon name="plus" />
                  Add New UBID
                </button>
              </div>
            </header>

            <section className="stats-grid ubid-stats-grid">
              <StatCard icon="grid" label="Total UBIDs" value={effectiveUbidStats.total_ubids.toLocaleString()} tone="blue" />
              <StatCard icon="check" label="Active UBIDs" value={effectiveUbidStats.active_ubids.toLocaleString()} tone="green" />
              <StatCard icon="archive" label="Inactive UBIDs" value={effectiveUbidStats.inactive_ubids.toLocaleString()} tone="blue" />
              <StatCard icon="trend" label="Under Review" value={effectiveUbidStats.under_review.toLocaleString()} tone="orange" />
              <StatCard icon="calendar" label="Created Today" value={effectiveUbidStats.created_today.toLocaleString()} tone="green" />
            </section>

            <section className="filters ubid-filters">
              <label className="search-field">
                Search UBID / Entity Name / PAN / GSTIN
                <input
                  value={ubidFilters.search}
                  onChange={(event) => setUbidFilters((current) => ({ ...current, search: event.target.value }))}
                  placeholder="Search..."
                />
              </label>
              <label>
                Status
                <select value={ubidFilters.status} onChange={(event) => setUbidFilters((current) => ({ ...current, status: event.target.value }))}>
                  <option>All</option>
                  <option value="ACTIVE">Active</option>
                  <option value="UNDER_REVIEW">Under Review</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </label>
              <label>
                Source Systems
                <select value={ubidFilters.sourceSystem} onChange={(event) => setUbidFilters((current) => ({ ...current, sourceSystem: event.target.value }))}>
                  <option>All</option>
                  {ubidSourceOptions.map((source) => (
                    <option key={source}>{source}</option>
                  ))}
                </select>
              </label>
              <button className="secondary-button" type="button" onClick={loadUbids}>
                <Icon name="search" />
                Filter
              </button>
              <button className="secondary-button" type="button" onClick={resetUbidFilters}>
                Reset
              </button>
            </section>

            {ubidError ? <div className="error-banner">{ubidError}</div> : null}

            <section className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>UBID</th>
                    <th>Entity Name</th>
                    <th>Constituent Count</th>
                    <th>Primary PAN</th>
                    <th>Primary GSTIN</th>
                    <th>Source Systems</th>
                    <th>Status</th>
                    <th>Match Confidence Avg</th>
                    <th>Created On</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isUbidLoading ? (
                    <tr>
                      <td colSpan="10" className="table-message">
                        Loading UBIDs...
                      </td>
                    </tr>
                  ) : ubids.length ? (
                    ubids.map((ubid) => (
                      <tr key={ubid.ubid}>
                        <td className="strong-cell">{ubid.ubid}</td>
                        <td>{ubid.entity_name || '-'}</td>
                        <td>{ubid.constituent_count || 0}</td>
                        <td>{ubid.primary_pan || '-'}</td>
                        <td>{ubid.primary_gstin || '-'}</td>
                        <td>{ubid.source_systems?.length ? ubid.source_systems.join(', ') : '-'}</td>
                        <td>
                          <Badge tone={ubidStatusTone(ubid.status)}>{statusLabel(ubid.status)}</Badge>
                        </td>
                        <td>
                          <Badge tone={Number(ubid.average_match_confidence || 0) >= 0.85 ? 'green' : 'amber'}>
                            {formatScore(ubid.average_match_confidence)}
                          </Badge>
                        </td>
                        <td>{formatDate(ubid.created_at)}</td>
                        <td>
                          <button className="icon-button" type="button" aria-label={`View ${ubid.ubid}`}>
                            <Icon name="search" />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="10" className="table-message">
                        No UBIDs match the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>

            <footer className="pagination-bar">
              <span>
                Showing {ubids.length ? 1 : 0} to {ubids.length} of {ubids.length} entries
              </span>
              <div className="pagination">
                <button type="button">‹</button>
                <button className="active" type="button">
                  1
                </button>
                <button type="button">2</button>
                <button type="button">3</button>
              </div>
              <select aria-label="Rows per page" defaultValue="5">
                <option>5</option>
                <option>10</option>
                <option>25</option>
              </select>
            </footer>
          </>
        ) : activeView === 'ubid-status' ? (
          <>
            <header className="topbar">
              <div>
                <h1>UBID Status Dashboard</h1>
                <p>Track computed business status and the event categories contributing to each score.</p>
              </div>
              <div className="top-actions">
                <button className="secondary-button" type="button" onClick={() => loadUbidStatuses()}>
                  <Icon name="refresh" />
                  Refresh
                </button>
              </div>
            </header>

            <section className="stats-grid ubid-status-stats-grid">
              <StatCard icon="grid" label="Tracked UBIDs" value={ubidStatusStats.total.toLocaleString()} tone="blue" />
              <StatCard icon="check" label="Active" value={ubidStatusStats.active.toLocaleString()} tone="green" />
              <StatCard icon="trend" label="Dormant" value={ubidStatusStats.dormant.toLocaleString()} tone="orange" />
              <StatCard icon="archive" label="Inactive" value={ubidStatusStats.inactive.toLocaleString()} tone="red" />
              <StatCard icon="document" label="Event Categories" value={ubidStatusStats.categories.toLocaleString()} tone="blue" />
            </section>

            <section className="filters ubid-status-filters">
              <label className="search-field">
                Search UBID
                <input
                  value={ubidStatusFilters.search}
                  onChange={(event) => setUbidStatusFilters((current) => ({ ...current, search: event.target.value }))}
                  placeholder="Enter UBID..."
                />
              </label>
              <label>
                Status
                <select value={ubidStatusFilters.status} onChange={(event) => setUbidStatusFilters((current) => ({ ...current, status: event.target.value }))}>
                  <option>All</option>
                  <option value="ACTIVE">Active</option>
                  <option value="DORMANT">Dormant</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={ubidStatusFilters.activeOnly}
                  onChange={(event) => setUbidStatusFilters((current) => ({ ...current, activeOnly: event.target.checked }))}
                />
                Active rows only
              </label>
              <button className="secondary-button" type="button" onClick={() => loadUbidStatuses(ubidStatusFilters)}>
                <Icon name="search" />
                Filter
              </button>
              <button className="secondary-button" type="button" onClick={resetUbidStatusFilters}>
                Reset
              </button>
            </section>

            {ubidStatusError ? <div className="error-banner">{ubidStatusError}</div> : null}

            <section className="table-wrap ubid-status-table">
              <table>
                <thead>
                  <tr>
                    <th>UBID</th>
                    <th>Status</th>
                    <th>Positive Score</th>
                    <th>Negative Score</th>
                    <th>Latest Event</th>
                    <th>Last Computation</th>
                    <th>Contribution Rows</th>
                    <th>Audit Row</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isUbidStatusLoading ? (
                    <tr>
                      <td colSpan="9" className="table-message">
                        Loading UBID statuses...
                      </td>
                    </tr>
                  ) : filteredUbidStatuses.length ? (
                    filteredUbidStatuses.map((statusRow) => {
                      const snapshotRows = statusRow.event_computation_snapshot || [];
                      const contributionRows = computationsByUbid[statusRow.ubid] || snapshotRows;
                      const isExpanded = expandedStatusUbid === String(statusRow.id);
                      return (
                        <Fragment key={statusRow.id}>
                          <tr key={statusRow.id}>
                            <td className="strong-cell">{statusRow.ubid}</td>
                            <td>
                              <Badge tone={ubidStatusTone(statusRow.status)}>{statusLabel(statusRow.status)}</Badge>
                            </td>
                            <td>
                              <Badge tone="green">{formatSignedNumber(statusRow.computed_positive_score)}</Badge>
                            </td>
                            <td>
                              <Badge tone={Number(statusRow.computed_negative_score || 0) < 0 ? 'red' : 'green'}>
                                {formatSignedNumber(statusRow.computed_negative_score)}
                              </Badge>
                            </td>
                            <td>{statusRow.latest_event_id || '-'}</td>
                            <td>{formatDate(statusRow.updated_at || statusRow.created_at)}</td>
                            <td>{contributionRows.length}</td>
                            <td>
                              <Badge tone={statusRow.is_active ? 'green' : 'amber'}>{statusRow.is_active ? 'Active' : 'Historical'}</Badge>
                            </td>
                            <td>
                              <button
                                className="review-button"
                                type="button"
                                onClick={() => setExpandedStatusUbid(isExpanded ? '' : String(statusRow.id))}
                              >
                                {isExpanded ? 'Hide' : 'Events'}
                              </button>
                            </td>
                          </tr>
                          {isExpanded ? (
                            <tr key={`${statusRow.id}-details`} className="contribution-row">
                              <td colSpan="9">
                                <div className="contribution-panel">
                                  <div className="contribution-header">
                                    <strong>Event contribution snapshot</strong>
                                    <span>
                                      Positive {formatSignedNumber(statusRow.computed_positive_score)} | Negative {formatSignedNumber(statusRow.computed_negative_score)}
                                    </span>
                                  </div>
                                  <div className="contribution-grid">
                                    {contributionRows.length ? (
                                      contributionRows.map((item) => (
                                        <article className="contribution-card" key={`${statusRow.id}-${item.event_category_id}`}>
                                          <div>
                                            <span className="eyebrow">Category</span>
                                            <strong>{item.event_category || item.event_category_id || '-'}</strong>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Score</span>
                                            <Badge tone={getContributionTone(item.score)}>{formatSignedNumber(item.score)}</Badge>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Base Weight</span>
                                            <strong>{formatSignedNumber(item.base_weight)}</strong>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Decay</span>
                                            <strong>{formatNumber(item.final_decay_constant, 4)}</strong>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Factor</span>
                                            <strong>{formatNumber(item.multiplication_decay_constant_factor, 4)}</strong>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Latest Event</span>
                                            <strong>{item.latest_event_id || '-'}</strong>
                                          </div>
                                          <div>
                                            <span className="eyebrow">Computed</span>
                                            <strong>{formatDate(item.updated_at || item.last_computed_date)}</strong>
                                          </div>
                                        </article>
                                      ))
                                    ) : (
                                      <p className="empty-state">No event category contribution rows found for this UBID.</p>
                                    )}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan="9" className="table-message">
                        No UBID statuses match the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </>
        ) : activeView === 'event-reviews' ? (
          <>
            <header className="topbar">
              <div>
                <h1>Event Review Dashboard</h1>
                <p>Review event-to-UBID candidate matches from the Event Engine.</p>
              </div>
              <div className="top-actions">
                <button className="secondary-button" type="button" onClick={() => loadEventReviews()}>
                  <Icon name="refresh" />
                  Refresh
                </button>
              </div>
            </header>

            <section className="stats-grid event-stats-grid">
              <StatCard icon="document" label="Total Events" value={effectiveEventStats.total_events.toLocaleString()} tone="blue" />
              <StatCard icon="flag" label="Pending Event Reviews" value={effectiveEventStats.pending_reviews.toLocaleString()} tone="orange" />
              <StatCard icon="calendar" label="Processed Today" value={effectiveEventStats.processed_today.toLocaleString()} tone="green" />
              <StatCard icon="chart" label="Event Types" value={effectiveEventStats.event_type_count.toLocaleString()} tone="blue" />
              <StatCard icon="grid" label="Matched UBIDs" value={effectiveEventStats.ubid_count.toLocaleString()} tone="green" />
            </section>

            <section className="filters event-review-filters">
              <label className="search-field">
                Search
                <input
                  value={eventReviewFilters.search}
                  onChange={(event) => setEventReviewFilters((current) => ({ ...current, search: event.target.value }))}
                  placeholder="Search event, UBID, GSTIN, PAN, source..."
                />
              </label>
              <label>
                Status
                <select value={eventReviewFilters.status} onChange={(event) => setEventReviewFilters((current) => ({ ...current, status: event.target.value }))}>
                  <option>All</option>
                  <option value="PENDING_REVIEW">Pending Review</option>
                </select>
              </label>
              <button className="secondary-button" type="button" onClick={() => loadEventReviews(eventReviewFilters)}>
                <Icon name="search" />
                Filter
              </button>
              <button className="secondary-button" type="button" onClick={resetEventReviewFilters}>
                Reset
              </button>
            </section>

            {eventReviewError ? <div className="error-banner">{eventReviewError}</div> : null}

            <section className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Review ID</th>
                    <th>Event ID</th>
                    <th>Event Type</th>
                    <th>Suggested UBID</th>
                    <th>Identity</th>
                    <th>Source</th>
                    <th>Entity</th>
                    <th>Match Type</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Created On</th>
                    <th>Map UBID</th>
                  </tr>
                </thead>
                <tbody>
                  {isEventReviewLoading ? (
                    <tr>
                      <td colSpan="12" className="table-message">
                        Loading event reviews...
                      </td>
                    </tr>
                  ) : eventReviews.length ? (
                    eventReviews.map((review) => (
                      <tr key={review.review_id}>
                        <td className="strong-cell">{review.review_id}</td>
                        <td>{review.event_id || '-'}</td>
                        <td>{review.event_type || '-'}</td>
                        <td>{review.suggested_ubid || '-'}</td>
                        <td>{getEventReviewIdentity(review)}</td>
                        <td>{review.source_name || '-'}</td>
                        <td>{review.name || '-'}</td>
                        <td>
                          <Badge tone={review.top_match_type === 'hard' ? 'green' : 'amber'}>{review.top_match_type || '-'}</Badge>
                        </td>
                        <td>
                          <Badge tone={Number(review.top_similarity_score || 0) >= 0.85 ? 'green' : 'amber'}>{formatScore(review.top_similarity_score)}</Badge>
                        </td>
                        <td>
                          <Badge tone={eventStatusTone(review.status)}>{statusLabel(review.status)}</Badge>
                        </td>
                        <td>{formatDate(review.created_at)}</td>
                        <td>
                          {review.status === 'PENDING_REVIEW' && review.candidates?.length ? (
                            <button className="review-button" type="button" onClick={() => setSelectedEventReview(review)}>
                              Review
                              <Icon name="chevron" />
                            </button>
                          ) : review.status === 'PENDING_REVIEW' ? (
                            <div className="inline-map-control">
                              <select
                                value={eventReviewSelections[review.review_id] || review.suggested_ubid || ''}
                                onChange={(event) =>
                                  setEventReviewSelections((current) => ({
                                    ...current,
                                    [review.review_id]: event.target.value,
                                  }))
                                }
                              >
                                <option value="">Select UBID</option>
                                {review.suggested_ubid ? <option value={review.suggested_ubid}>{review.suggested_ubid} - Suggested</option> : null}
                                {eventReviewUbidOptions.map((ubid) => (
                                  <option key={ubid.ubid} value={ubid.ubid}>
                                    {ubid.ubid} - {ubid.entity_name || 'Unnamed'}
                                  </option>
                                ))}
                              </select>
                              <button
                                className="review-button"
                                type="button"
                                onClick={() => resolveEventReview(review)}
                                disabled={resolvingEventReviewId === review.review_id}
                              >
                                {resolvingEventReviewId === review.review_id ? 'Saving...' : 'Map'}
                              </button>
                            </div>
                          ) : (
                            review.resolved_ubid || '-'
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="12" className="table-message">
                        No event reviews match the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </>
        ) : activeView === 'event-master' ? (
          <>
            <header className="topbar">
              <div>
                <h1>Event Master Dashboard</h1>
                <p>Browse processed events and their latest UBID decision outcomes.</p>
              </div>
              <div className="top-actions">
                <button className="secondary-button" type="button" onClick={() => loadEvents()}>
                  <Icon name="refresh" />
                  Refresh
                </button>
              </div>
            </header>

            <section className="stats-grid event-stats-grid">
              <StatCard icon="document" label="Total Events" value={effectiveEventStats.total_events.toLocaleString()} tone="blue" />
              <StatCard icon="calendar" label="Processed Today" value={effectiveEventStats.processed_today.toLocaleString()} tone="green" />
              <StatCard icon="chart" label="Event Types" value={effectiveEventStats.event_type_count.toLocaleString()} tone="blue" />
              <StatCard icon="grid" label="Matched UBIDs" value={effectiveEventStats.ubid_count.toLocaleString()} tone="green" />
              <StatCard icon="flag" label="Pending Reviews" value={effectiveEventStats.pending_reviews.toLocaleString()} tone="orange" />
            </section>

            <section className="filters event-filters">
              <label className="search-field">
                Search Event / Entity / PAN / GSTIN
                <input
                  value={eventFilters.search}
                  onChange={(event) => setEventFilters((current) => ({ ...current, search: event.target.value }))}
                  placeholder="Search..."
                />
              </label>
              <label>
                Event Type
                <select value={eventFilters.eventType} onChange={(event) => setEventFilters((current) => ({ ...current, eventType: event.target.value }))}>
                  <option>All</option>
                  {eventTypeOptions.map((eventType) => (
                    <option key={eventType}>{eventType}</option>
                  ))}
                </select>
              </label>
              <label>
                Source
                <select value={eventFilters.sourceName} onChange={(event) => setEventFilters((current) => ({ ...current, sourceName: event.target.value }))}>
                  <option>All</option>
                  {eventSourceOptions.map((source) => (
                    <option key={source}>{source}</option>
                  ))}
                </select>
              </label>
              <button className="secondary-button" type="button" onClick={() => loadEvents(eventFilters)}>
                <Icon name="search" />
                Filter
              </button>
              <button className="secondary-button" type="button" onClick={resetEventFilters}>
                Reset
              </button>
            </section>

            {eventError ? <div className="error-banner">{eventError}</div> : null}

            <section className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Event ID</th>
                    <th>Event Type</th>
                    <th>Identity</th>
                    <th>Entity Name</th>
                    <th>Source</th>
                    <th>Address</th>
                    <th>Pincode</th>
                    <th>Decision</th>
                    <th>Matched UBID</th>
                    <th>Confidence</th>
                    <th>Processed On</th>
                  </tr>
                </thead>
                <tbody>
                  {isEventLoading ? (
                    <tr>
                      <td colSpan="11" className="table-message">
                        Loading events...
                      </td>
                    </tr>
                  ) : events.length ? (
                    events.map((event) => (
                      <tr key={event.id || event.event_id}>
                        <td className="strong-cell">{event.event_id || event.id}</td>
                        <td>{event.event_type || '-'}</td>
                        <td>{getEventIdentity(event)}</td>
                        <td>{event.name || '-'}</td>
                        <td>{event.source_name || '-'}</td>
                        <td className="wide-cell">{event.address || '-'}</td>
                        <td>{event.pincode || '-'}</td>
                        <td>
                          <Badge tone={eventStatusTone(event.decision_status)}>{statusLabel(event.decision_status || 'NO_MATCH')}</Badge>
                        </td>
                        <td>{event.matched_ubid || event.ubid || '-'}</td>
                        <td>
                          <Badge tone={Number(event.top_similarity_score || 0) >= 0.85 ? 'green' : 'amber'}>{formatScore(event.top_similarity_score)}</Badge>
                        </td>
                        <td>{formatDate(event.processed_at)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="11" className="table-message">
                        No events match the current filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>
          </>
        ) : (
          <>
        <header className="topbar">
          <div>
            <h1>UBID Resolution Review Dashboard</h1>
            <p>Resolve identity conflicts from department record matching.</p>
          </div>
          <div className="top-actions">
            <button className="secondary-button" type="button" onClick={loadReviews}>
              <Icon name="refresh" />
              Refresh
            </button>
            <button className="secondary-button" type="button">
              <Icon name="calendar" />
              01 May 2024 - 10 May 2024
            </button>
          </div>
        </header>

        <section className="stats-grid">
          <StatCard icon="document" label="Total Pending Reviews" value={stats.pending.toLocaleString()} tone="orange" />
          <StatCard icon="flag" label="High Priority" value={stats.high.toLocaleString()} tone="red" />
          <StatCard icon="check" label="Reviewed Today" value={stats.reviewed.toLocaleString()} tone="green" />
          <StatCard icon="check" label="Approved" value={stats.approved.toLocaleString()} tone="green" />
          <StatCard icon="x" label="New UBID Decisions" value={stats.rejected.toLocaleString()} tone="red" />
          <StatCard icon="clock" label="Avg Resolution Time" value="2h 45m" tone="blue" />
        </section>

        <section className="filters">
          <label>
            Match Confidence
            <select value={filters.confidence} onChange={(event) => setFilters((current) => ({ ...current, confidence: event.target.value }))}>
              <option>All</option>
              <option>90+</option>
              <option>80-90</option>
              <option>70-80</option>
              <option>&lt;70</option>
            </select>
          </label>
          <label className="search-field">
            Search
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search by UBID, entity name, PAN, GSTIN..."
            />
          </label>
          <button className="primary-button" type="button">
            <Icon name="search" />
            Search
          </button>
          <button className="secondary-button" type="button" onClick={resetFilters}>
            Reset
          </button>
        </section>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input type="checkbox" aria-label="Select all reviews" />
                </th>
                <th>Review ID</th>
                <th>UBID Proposed</th>
                <th>Entity Name</th>
                <th>Source System</th>
                <th>Match Confidence</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Created On</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan="10" className="table-message">
                    Loading reviews...
                  </td>
                </tr>
              ) : filteredReviews.length ? (
                filteredReviews.map((review) => {
                  const priority = getPriority(review);
                  return (
                    <tr key={review.review_id}>
                      <td>
                        <input type="checkbox" aria-label={`Select ${review.review_id}`} />
                      </td>
                      <td className="strong-cell">{review.review_id}</td>
                      <td>{review.suggested_ubid || review.resolved_ubid || '-'}</td>
                      <td>{getEntityName(review)}</td>
                      <td>{getSourceSystem(review)}</td>
                      <td>
                        <Badge tone={getScore(review) >= 0.85 ? 'green' : 'amber'}>{formatScore(review.top_similarity_score)}</Badge>
                      </td>
                      <td>
                        <Badge tone={priority === 'High' ? 'red' : priority === 'Medium' ? 'amber' : 'green'}>{priority}</Badge>
                      </td>
                      <td>
                        <Badge tone={review.status === 'PENDING_REVIEW' ? 'amber' : 'green'}>{statusLabel(review.status)}</Badge>
                      </td>
                      <td>{formatDate(review.created_at)}</td>
                      <td>
                        <button className="review-button" type="button" onClick={() => setSelectedReview(review)}>
                          Review
                          <Icon name="chevron" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="10" className="table-message">
                    No reviews match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <footer className="pagination-bar">
          <span>
            Showing {filteredReviews.length ? 1 : 0} to {filteredReviews.length} of {reviews.length} entries
          </span>
          <div className="pagination">
            <button type="button">‹</button>
            <button className="active" type="button">
              1
            </button>
            <button type="button">2</button>
            <button type="button">3</button>
            <button type="button">...</button>
          </div>
          <select aria-label="Rows per page" defaultValue="5">
            <option>5</option>
            <option>10</option>
            <option>25</option>
          </select>
        </footer>
          </>
        )}
      </main>

      {activeView === 'review' ? <ResolutionPanel review={selectedReview} onClose={() => setSelectedReview(null)} onResolved={handleResolved} /> : null}
      {activeView === 'event-reviews' ? (
        <EventResolutionPanel review={selectedEventReview} onClose={() => setSelectedEventReview(null)} onResolved={handleEventReviewResolved} />
      ) : null}
    </div>
  );
}

export default App;
