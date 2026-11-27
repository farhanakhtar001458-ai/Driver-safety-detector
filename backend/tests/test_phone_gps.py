"""Phone GPS consent and authorisation endpoints."""
from app.models import DrivingEvent, VehicleLocation


def test_phone_gps_requires_auth(client):
    assert client.get('/api/v1/gps/phone/vehicles').status_code == 401
    assert client.post('/api/v1/gps/phone', json={'vehicle_id': 1, 'latitude': 1, 'longitude': 2, 'accuracy_m': 10}).status_code == 401


def test_phone_gps_driver_only_assigned_vehicle(client, driver_headers, db):
    response = client.get('/api/v1/gps/phone/vehicles', headers=driver_headers)
    assert response.status_code == 200
    assert [v['id'] for v in response.json()] == [1]
    point = {'vehicle_id': 1, 'latitude': 23.25, 'longitude': 77.4, 'accuracy_m': 12}
    before = db.query(DrivingEvent).count()
    response = client.post('/api/v1/gps/phone', headers=driver_headers, json=point)
    assert response.status_code == 201, response.text
    db.expire_all()
    row = db.query(VehicleLocation).filter(VehicleLocation.source == 'phone', VehicleLocation.vehicle_id == 1).order_by(VehicleLocation.id.desc()).first()
    assert row is not None and not row.is_simulated and row.device_id is None
    assert db.query(DrivingEvent).count() == before
    assert client.post('/api/v1/gps/phone', headers=driver_headers, json={**point, 'vehicle_id': 2}).status_code == 404
    assert client.post('/api/v1/gps/phone', headers=driver_headers, json={**point, 'latitude': 91}).status_code == 422
    db.delete(row)
    db.commit()


def test_phone_gps_cross_tenant_denied(client, admin_headers):
    import uuid
    suffix = uuid.uuid4().hex[:8]
    signup = client.post('/api/v1/auth/register', json={'email': f'phone-{suffix}@example.com', 'password': 'StrongPass!2026', 'full_name': 'Fleet Admin', 'organisation_name': f'Phone Fleet {suffix}'})
    assert signup.status_code == 201, signup.text
    token = signup.json()['token']['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    assert client.get('/api/v1/gps/phone/vehicles', headers=headers).json() == []
    result = client.post('/api/v1/gps/phone', headers=headers, json={'vehicle_id': 1, 'latitude': 23, 'longitude': 77, 'accuracy_m': 10})
    assert result.status_code == 404
