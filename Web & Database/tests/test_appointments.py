"""Appointment requests between a patient and their own instructor."""
from datetime import datetime, timedelta

import app as motion
from conftest import login


def future(days=7, hour=10):
    t = (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return t.strftime("%Y-%m-%dT%H:%M")  # format sent by <input type="datetime-local">


def past():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")


def request_appointment(client, slots, note="Check-in"):
    return client.post("/appointments/new", data={"slots": slots, "note": note})


def only_appointment(make):
    with make.app.app_context():
        a = motion.Appointment.query.one()
        return a.id, a.status, a.requester_id, a.recipient_id, [s.id for s in a.slots]


def test_patient_requests_appointment_with_own_instructor(client, make, people):
    login(client, "patA")
    r = request_appointment(client, [future(1), future(2)])
    assert r.status_code == 302
    _, status, requester, recipient, slots = only_appointment(make)
    assert (status, requester, recipient, len(slots)) == ("pending", people["pat_a"], people["ins_a"], 2)


def test_past_times_are_ignored(client, make, people):
    login(client, "patA")
    r = request_appointment(client, [past()])
    assert b"future" in r.data
    assert make.count(motion.Appointment) == 0


def test_duplicate_slots_are_merged(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1), future(1)])
    assert len(only_appointment(make)[4]) == 1


def test_instructor_cannot_book_another_instructors_patient(client, make, people):
    login(client, "insA")
    r = client.get(f"/appointments/new?patient_id={people['pat_b']}")
    assert r.status_code == 404


def test_instructor_approves_one_slot(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1), future(2)])
    aid, _, _, _, slots = only_appointment(make)
    client.post("/logout")

    login(client, "insA")
    client.post(f"/appointments/{aid}/respond", data={"action": "approve", "slot_id": str(slots[1])})
    a = make.get(motion.Appointment, aid)
    assert a.status == "approved"
    assert a.selected_slot_id == slots[1]


def test_requester_cannot_approve_own_request(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1)])
    aid, _, _, _, slots = only_appointment(make)
    r = client.post(f"/appointments/{aid}/respond", data={"action": "approve", "slot_id": str(slots[0])})
    assert r.status_code == 403


def test_counter_proposal_swaps_requester_and_recipient(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1)])
    aid = only_appointment(make)[0]
    client.post("/logout")

    login(client, "insA")
    client.post(f"/appointments/{aid}/respond", data={"action": "counter", "slots": [future(3)]})
    _, status, requester, recipient, slots = only_appointment(make)
    assert (status, requester, recipient, len(slots)) == ("pending", people["ins_a"], people["pat_a"], 1)


def test_decline_and_then_cancel_is_forbidden(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1)])
    aid = only_appointment(make)[0]
    client.post("/logout")

    login(client, "insA")
    client.post(f"/appointments/{aid}/respond", data={"action": "decline"})
    assert make.get(motion.Appointment, aid).status == "declined"
    assert client.post(f"/appointments/{aid}/cancel").status_code == 403


def test_unrelated_user_cannot_cancel(client, make, people):
    login(client, "patA")
    request_appointment(client, [future(1)])
    aid = only_appointment(make)[0]
    client.post("/logout")

    login(client, "patB")
    assert client.post(f"/appointments/{aid}/cancel").status_code == 403
    assert make.get(motion.Appointment, aid).status == "pending"
