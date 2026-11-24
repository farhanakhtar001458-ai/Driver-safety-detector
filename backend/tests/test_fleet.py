"""Vehicle, driver, RBAC and tenant-isolation tests."""

from __future__ import annotations

import uuid

import pytest


def _unique_registration() -> str:
    return f"MP09 TS {uuid.uuid4().hex[:4].upper()}"


def test_vehicle_crud_lifecycle(client, admin_headers):
    registration = _unique_registration()
    create = client.post(
        "/api/v1/vehicles",
        json={
            "registration_number": registration,
            "vehicle_type": "van",
            "manufacturer": "Force Motors",
            "model": "Traveller",
            "manufacturing_year": 2022,
            "fuel_type": "diesel",
            "mileage_km": 45000,
            "vin": "MH12ABCD123456789",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    vehicle = create.json()
    assert vehicle["registration_number"] == registration.replace(" ", "")
    assert vehicle["vin_masked"].endswith("6789")
    assert len(vehicle["vin_masked"]) == 17

    vehicle_id = vehicle["id"]

    listing = client.get("/api/v1/vehicles", params={"search": registration.replace(" ", "")}, headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    update = client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        json={"status": "under_maintenance", "notes": "Brake inspection"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.json()["status"] == "under_maintenance"

    assign = client.post(
        f"/api/v1/vehicles/{vehicle_id}/assign-driver", json={"driver_id": 1}, headers=admin_headers
    )
    assert assign.status_code == 200
    assert assign.json()["assigned_driver_id"] == 1

    detail = client.get(f"/api/v1/vehicles/{vehicle_id}/overview", headers=admin_headers)
    assert detail.status_code == 200
    assert "vehicle" in detail.json()

    archive = client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=admin_headers)
    assert archive.status_code == 200
    assert client.get(f"/api/v1/vehicles/{vehicle_id}", headers=admin_headers).json()["is_archived"] is True


def test_duplicate_registration_rejected(client, admin_headers):
    payload = {
        "registration_number": "MP09 AB 4211",
        "vehicle_type": "truck",
        "manufacturer": "Tata",
        "model": "Prima",
        "manufacturing_year": 2021,
        "fuel_type": "diesel",
    }
    response = client.post("/api/v1/vehicles", json=payload, headers=admin_headers)
    assert response.status_code == 409


def test_vehicle_input_validation(client, admin_headers):
    base = {
        "registration_number": "MP09 BAD 0001",
        "vehicle_type": "car",
        "manufacturer": "Test",
        "model": "Model",
        "manufacturing_year": 2022,
        "fuel_type": "petrol",
    }
    bad_vin = client.post("/api/v1/vehicles", json={**base, "vin": "SHORT"}, headers=admin_headers)
    assert bad_vin.status_code == 422
    bad_status = client.post("/api/v1/vehicles", json={**base, "status": "flying"}, headers=admin_headers)
    assert bad_status.status_code == 422
    bad_year = client.post("/api/v1/vehicles", json={**base, "manufacturing_year": 1900}, headers=admin_headers)
    assert bad_year.status_code == 422


def test_driver_crud_and_masked_pii(client, admin_headers):
    create = client.post(
        "/api/v1/drivers",
        json={
            "first_name": "Test",
            "last_name": "Driver",
            "phone": "9876543210",
            "licence_number": "MP09 2020 0011223",
            "licence_expiry": "2027-01-01",
            "years_experience": 3,
            "status": "active",
        },
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    driver = create.json()
    assert driver["phone_masked"].endswith("3210")
    assert "*" in driver["phone_masked"]
    assert driver["licence_number_masked"].endswith("1223")
    # Raw values must never be exposed by the list/detail endpoints.
    assert "licence_number_encrypted" not in driver
    assert "9876543210" not in str(driver)

    driver_id = driver["id"]
    profile = client.get(f"/api/v1/drivers/{driver_id}/profile", headers=admin_headers)
    assert profile.status_code == 200
    assert profile.json()["driver"]["id"] == driver_id

    deactivate = client.delete(f"/api/v1/drivers/{driver_id}", headers=admin_headers)
    assert deactivate.status_code == 200


def test_driver_role_cannot_create_vehicles(client, driver_headers):
    response = client.post(
        "/api/v1/vehicles",
        json={
            "registration_number": "MP09 DRIVER 01",
            "vehicle_type": "car",
            "manufacturer": "A",
            "model": "B",
            "manufacturing_year": 2020,
            "fuel_type": "petrol",
        },
        headers=driver_headers,
    )
    assert response.status_code == 403
    assert "vehicles:create" in response.json()["error"]["message"]


def test_driver_cannot_read_incidents(client, driver_headers):
    response = client.get("/api/v1/incidents", headers=driver_headers)
    assert response.status_code == 403


def test_driver_can_read_own_scores(client, driver_headers):
    response = client.get("/api/v1/drivers/1/scores", headers=driver_headers)
    assert response.status_code == 200
    assert "disclaimer" in response.json()


def test_tenant_isolation_between_organisations(client, admin_headers):
    suffix = uuid.uuid4().hex[:6]
    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"other-{suffix}@example.com",
            "password": "StrongPass!2026",
            "full_name": "Other Admin",
            "organisation_name": f"Other Fleet {suffix}",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other['token']['access_token']}"}

    # Other tenant's vehicle list must be empty and must not reveal demo rows.
    assert client.get("/api/v1/vehicles", headers=other_headers).json()["total"] == 0
    assert client.get("/api/v1/drivers", headers=other_headers).json()["total"] == 0

    # Direct object access by ID must 404 rather than leak data.
    assert client.get("/api/v1/vehicles/1", headers=other_headers).status_code == 404
    assert client.get("/api/v1/drivers/1/profile", headers=other_headers).status_code == 404
    assert client.get("/api/v1/incidents/1", headers=other_headers).status_code == 404

    # Mutation attempts must also fail.
    assert (
        client.patch("/api/v1/vehicles/1", json={"status": "offline"}, headers=other_headers).status_code
        == 404
    )


def test_super_admin_can_list_all_organisations(client, superadmin_headers):
    response = client.get("/api/v1/organisations", headers=superadmin_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_super_admin_cannot_use_tenant_scoped_endpoint(client, superadmin_headers):
    # Super admins must select an organisation instead of silently using one.
    response = client.get("/api/v1/organisations/me", headers=superadmin_headers)
    assert response.status_code == 400


def test_team_creation_role_guard(client, admin_headers):
    # org_admin may create a driver, but may not create a super admin.
    ok = client.post(
        "/api/v1/organisations/me/team",
        json={
            "email": f"newdriver-{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPass!2026",
            "full_name": "New Driver",
            "role": "driver",
        },
        headers=admin_headers,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["permissions"]  # permission list is resolved server-side


def test_org_admin_cannot_assign_unmanageable_role(client, admin_headers):
    response = client.post(
        "/api/v1/organisations/me/team",
        json={
            "email": f"bad-{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPass!2026",
            "full_name": "Bad Role",
            "role": "super_admin",
        },
        headers=admin_headers,
    )
    assert response.status_code == 403
