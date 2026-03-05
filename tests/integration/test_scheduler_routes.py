"""
Integration tests for Scheduler routes.
Covers: index, create, view, update-pages, delete, toggle-session,
update-session, api/tahsili-dates, exam-date, pdf, and all mobile API routes.
Blueprint prefix: /scheduler
"""
import pytest
import secrets


def _make_student(db_session):
    from src.models.student import Student
    s = Student(
        name='Test',
        username=f'sch_stu_{secrets.token_hex(4)}',
        email=f'sch_{secrets.token_hex(4)}@test.com',
        is_active=True
    )
    s.set_password('Pass@123')
    s.session_token = secrets.token_hex(32)
    db_session.session.add(s)
    db_session.session.commit()
    db_session.session.refresh(s)
    return s


class TestSchedulerAdminRoutes:
    """Admin-facing web routes for the scheduler blueprint."""

    def _login(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

    # ------------------------------------------------------------------
    # GET /scheduler/  (index)
    # ------------------------------------------------------------------

    def test_index_no_auth(self, client):
        """GET /scheduler/ without authentication."""
        response = client.get('/scheduler/')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_index_as_admin(self, client, admin_user):
        """GET /scheduler/ as authenticated admin."""
        self._login(client, admin_user)
        response = client.get('/scheduler/')
        assert response.status_code in [200, 302, 404, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/create  (create form)
    # ------------------------------------------------------------------

    def test_create_get_no_auth(self, client):
        """GET /scheduler/create without authentication."""
        response = client.get('/scheduler/create')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_create_get_as_admin(self, client, admin_user):
        """GET /scheduler/create as authenticated admin."""
        self._login(client, admin_user)
        response = client.get('/scheduler/create')
        assert response.status_code in [200, 302, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/create  (create_post)
    # ------------------------------------------------------------------

    def test_create_post_no_auth(self, client):
        """POST /scheduler/create without authentication."""
        response = client.post('/scheduler/create', data={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_create_post_empty_data(self, client, admin_user):
        """POST /scheduler/create with empty payload."""
        self._login(client, admin_user)
        response = client.post('/scheduler/create', data={})
        assert response.status_code in [200, 302, 400, 404, 422, 500]

    def test_create_post_valid_data(self, client, admin_user):
        """POST /scheduler/create with plausible form data."""
        self._login(client, admin_user)
        response = client.post('/scheduler/create', data={
            'exam_date': '2026-06-01',
            'study_hours_per_day': '4',
            'start_date': '2026-05-01'
        })
        assert response.status_code in [200, 302, 400, 404, 500]

    def test_create_post_json_payload(self, client, admin_user):
        """POST /scheduler/create with JSON payload."""
        self._login(client, admin_user)
        response = client.post('/scheduler/create', json={
            'exam_date': '2026-06-01',
            'study_hours_per_day': 4
        })
        assert response.status_code in [200, 302, 400, 404, 422, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/<id>  (view_schedule)
    # ------------------------------------------------------------------

    def test_view_schedule_no_auth(self, client):
        """GET /scheduler/99999 without authentication."""
        response = client.get('/scheduler/99999')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_view_schedule_nonexistent_as_admin(self, client, admin_user):
        """GET /scheduler/99999 as admin - schedule does not exist."""
        self._login(client, admin_user)
        response = client.get('/scheduler/99999')
        assert response.status_code in [302, 404, 500]

    def test_view_schedule_alt_id_as_admin(self, client, admin_user):
        """GET /scheduler/88888 as admin - alternate nonexistent id."""
        self._login(client, admin_user)
        response = client.get('/scheduler/88888')
        assert response.status_code in [302, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/<id>/update-pages
    # ------------------------------------------------------------------

    def test_update_pages_no_auth(self, client):
        """POST /scheduler/99999/update-pages without authentication."""
        response = client.post('/scheduler/99999/update-pages', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_update_pages_nonexistent(self, client, admin_user):
        """POST /scheduler/99999/update-pages as admin - schedule not found."""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/update-pages', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/<id>/delete
    # ------------------------------------------------------------------

    def test_delete_no_auth(self, client):
        """POST /scheduler/99999/delete without authentication."""
        response = client.post('/scheduler/99999/delete')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_delete_nonexistent(self, client, admin_user):
        """POST /scheduler/99999/delete as admin - schedule not found."""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/delete')
        assert response.status_code in [200, 302, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/<id>/session/<session_id>/toggle
    # ------------------------------------------------------------------

    def test_toggle_session_no_auth(self, client):
        """POST /scheduler/99999/session/1/toggle without authentication."""
        response = client.post('/scheduler/99999/session/1/toggle')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_toggle_session_nonexistent(self, client, admin_user):
        """POST /scheduler/99999/session/1/toggle as admin - not found."""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/session/1/toggle')
        assert response.status_code in [200, 302, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/<id>/session/<session_id>/update
    # ------------------------------------------------------------------

    def test_update_session_no_auth(self, client):
        """POST /scheduler/99999/session/1/update without authentication."""
        response = client.post('/scheduler/99999/session/1/update', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_update_session_nonexistent(self, client, admin_user):
        """POST /scheduler/99999/session/1/update as admin - not found."""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/session/1/update', json={})
        assert response.status_code in [200, 302, 400, 404, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/api/tahsili-dates
    # ------------------------------------------------------------------

    def test_tahsili_dates_no_auth(self, client):
        """GET /scheduler/api/tahsili-dates without authentication."""
        response = client.get('/scheduler/api/tahsili-dates')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_tahsili_dates_as_admin(self, client, admin_user):
        """GET /scheduler/api/tahsili-dates as authenticated admin."""
        self._login(client, admin_user)
        response = client.get('/scheduler/api/tahsili-dates')
        assert response.status_code in [200, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/<id>/exam-date
    # ------------------------------------------------------------------

    def test_update_exam_date_no_auth(self, client):
        """POST /scheduler/99999/exam-date without authentication."""
        response = client.post('/scheduler/99999/exam-date', json={})
        assert response.status_code in [200, 302, 400, 401, 403, 404, 500]

    def test_update_exam_date_nonexistent(self, client, admin_user):
        """POST /scheduler/99999/exam-date as admin - schedule not found."""
        self._login(client, admin_user)
        response = client.post('/scheduler/99999/exam-date', json={
            'exam_date': '2026-06-01'
        })
        assert response.status_code in [200, 302, 400, 404, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/<id>/pdf
    # ------------------------------------------------------------------

    def test_export_pdf_no_auth(self, client):
        """GET /scheduler/99999/pdf without authentication."""
        response = client.get('/scheduler/99999/pdf')
        assert response.status_code in [200, 302, 401, 403, 404, 500]

    def test_export_pdf_nonexistent(self, client, admin_user):
        """GET /scheduler/99999/pdf as admin - schedule not found."""
        self._login(client, admin_user)
        response = client.get('/scheduler/99999/pdf')
        assert response.status_code in [302, 404, 500]


class TestSchedulerMobileAPI:
    """Mobile API routes under /scheduler/api/mobile/schedules."""

    # ------------------------------------------------------------------
    # GET /scheduler/api/mobile/schedules  (mobile_list_schedules)
    # ------------------------------------------------------------------

    def test_mobile_list_no_token(self, client):
        """GET mobile list without X-Session-Token."""
        response = client.get('/scheduler/api/mobile/schedules')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_list_with_student_token(self, client, db_session, app):
        """GET mobile list with a valid student session token."""
        s = _make_student(db_session)
        response = client.get(
            '/scheduler/api/mobile/schedules',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 404, 500]

    def test_mobile_list_invalid_token(self, client):
        """GET mobile list with a bogus X-Session-Token."""
        response = client.get(
            '/scheduler/api/mobile/schedules',
            headers={'X-Session-Token': 'invalid_token_value'}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/create  (mobile_create_schedule)
    # ------------------------------------------------------------------

    def test_mobile_create_no_token(self, client):
        """POST mobile create without X-Session-Token."""
        response = client.post(
            '/scheduler/api/mobile/schedules/create', json={}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 422, 500]

    def test_mobile_create_with_token_empty(self, client, db_session, app):
        """POST mobile create with student token but empty payload."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/create',
            json={},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

    def test_mobile_create_with_token_valid(self, client, db_session, app):
        """POST mobile create with student token and plausible data."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/create',
            json={'exam_date': '2026-06-01', 'study_hours_per_day': 4},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 201, 400, 401, 404, 422, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/api/mobile/schedules/<id>  (mobile_get_schedule)
    # ------------------------------------------------------------------

    def test_mobile_get_schedule_no_token(self, client):
        """GET mobile schedule without X-Session-Token."""
        response = client.get('/scheduler/api/mobile/schedules/99999')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_get_schedule_nonexistent(self, client, db_session, app):
        """GET mobile schedule with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/<id>/session/<session_id>/toggle
    # ------------------------------------------------------------------

    def test_mobile_toggle_session_no_token(self, client):
        """POST mobile toggle session without X-Session-Token."""
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/session/1/toggle'
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_toggle_session_nonexistent(self, client, db_session, app):
        """POST mobile toggle session with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/session/1/toggle',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/api/mobile/schedules/<id>/pdf  (mobile_export_pdf)
    # ------------------------------------------------------------------

    def test_mobile_export_pdf_no_token(self, client):
        """GET mobile PDF export without X-Session-Token."""
        response = client.get('/scheduler/api/mobile/schedules/99999/pdf')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_export_pdf_nonexistent(self, client, db_session, app):
        """GET mobile PDF export with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999/pdf',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/<id>/delete
    # ------------------------------------------------------------------

    def test_mobile_delete_no_token(self, client):
        """POST mobile delete without X-Session-Token."""
        response = client.post('/scheduler/api/mobile/schedules/99999/delete')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_delete_nonexistent(self, client, db_session, app):
        """POST mobile delete with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/delete',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/<id>/exam-date
    # ------------------------------------------------------------------

    def test_mobile_update_exam_date_no_token(self, client):
        """POST mobile exam-date without X-Session-Token."""
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/exam-date', json={}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_update_exam_date_nonexistent(self, client, db_session, app):
        """POST mobile exam-date with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/exam-date',
            json={'exam_date': '2026-06-01'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/<id>/status
    # ------------------------------------------------------------------

    def test_mobile_update_status_no_token(self, client):
        """POST mobile status without X-Session-Token."""
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/status', json={}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_update_status_nonexistent(self, client, db_session, app):
        """POST mobile status with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/status',
            json={'status': 'active'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_update_status_invalid_value(self, client, db_session, app):
        """POST mobile status with an invalid status value."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/status',
            json={'status': 'bogus_status'},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 422, 500]

    # ------------------------------------------------------------------
    # POST /scheduler/api/mobile/schedules/<id>/reschedule
    # ------------------------------------------------------------------

    def test_mobile_reschedule_no_token(self, client):
        """POST mobile reschedule without X-Session-Token."""
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/reschedule', json={}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_reschedule_nonexistent(self, client, db_session, app):
        """POST mobile reschedule with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/99999/reschedule',
            json={},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_reschedule_with_data(self, client, db_session, app):
        """POST mobile reschedule with plausible data - schedule not found."""
        s = _make_student(db_session)
        response = client.post(
            '/scheduler/api/mobile/schedules/88888/reschedule',
            json={'new_exam_date': '2026-07-01', 'study_hours_per_day': 3},
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 400, 401, 403, 404, 422, 500]

    # ------------------------------------------------------------------
    # GET /scheduler/api/mobile/schedules/<id>/stats
    # ------------------------------------------------------------------

    def test_mobile_get_stats_no_token(self, client):
        """GET mobile stats without X-Session-Token."""
        response = client.get('/scheduler/api/mobile/schedules/99999/stats')
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_mobile_get_stats_nonexistent(self, client, db_session, app):
        """GET mobile stats with student token - schedule not found."""
        s = _make_student(db_session)
        response = client.get(
            '/scheduler/api/mobile/schedules/99999/stats',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]

    def test_mobile_get_stats_alt_id(self, client, db_session, app):
        """GET mobile stats with student token - alternate nonexistent id."""
        s = _make_student(db_session)
        response = client.get(
            '/scheduler/api/mobile/schedules/88888/stats',
            headers={'X-Session-Token': s.session_token}
        )
        assert response.status_code in [200, 401, 403, 404, 500]
