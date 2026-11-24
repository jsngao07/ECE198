"""Fresh, patient-scoped dosage values for the Arduino v4 protocol."""
import pytest
import app as motion
from conftest import login


def configure(app, plan_id, **values):
    with app.app_context():
        plan = motion.db.session.get(motion.ExercisePlan, plan_id)
        for name, value in values.items():
            setattr(plan, name, value)
        motion.db.session.commit()


@pytest.mark.parametrize('name,index', [('Arm Curl', 0), ('Front Arm Raise', 1), ('Lateral Arm Raise', 2)])
def test_firmware_mapping_and_minutes_to_seconds(app, client, make, people, name, index):
    plan = make.plan(people['pat_a'], people['ins_a'], name)
    configure(app, plan, reps=20, duration_minutes=2)
    login(client, 'patA')
    response = client.get(f'/api/device/plans/{plan}')
    assert response.status_code == 200
    assert response.json['command'] == f'SET,{index},20,120\n'
    assert response.json['sets'] == 3  # Do not silently multiply reps by sets.
    assert response.headers['Cache-Control'].startswith('no-store')
    configure(app, plan, reps=25)
    assert client.get(f'/api/device/plans/{plan}').json['reps'] == 25


@pytest.mark.parametrize('values', [dict(duration_minutes=None), dict(duration_minutes=0),
                                  dict(duration_minutes=61), dict(reps=0), dict(reps=1001)])
def test_invalid_or_missing_dosage_rejected(app, client, make, people, values):
    plan = make.plan(people['pat_a'], people['ins_a'])
    configure(app, plan, duration_minutes=1)
    configure(app, plan, **values)
    login(client, 'patA')
    assert client.get(f'/api/device/plans/{plan}').status_code == 422


def test_maximum_dosage(app, client, make, people):
    plan = make.plan(people['pat_a'], people['ins_a'])
    configure(app, plan, reps=1000, duration_minutes=60)
    login(client, 'patA')
    assert client.get(f'/api/device/plans/{plan}').json['command'] == 'SET,0,1000,3600\n'


def test_other_patient_inactive_and_missing_plans_are_hidden(app, client, make, people):
    foreign = make.plan(people['pat_b'], people['ins_b'])
    inactive = make.plan(people['pat_a'], people['ins_a'], active=False)
    login(client, 'patA')
    for plan in [foreign, inactive, 999999]:
        assert client.get(f'/api/device/plans/{plan}').status_code == 404


def test_unsupported_exercise(client, make, people):
    plan = make.plan(people['pat_a'], people['ins_a'], 'Leg Raise')
    login(client, 'patA')
    assert client.get(f'/api/device/plans/{plan}').status_code == 422


def test_authentication_and_role_required(client, make, people):
    plan = make.plan(people['pat_a'], people['ins_a'])
    assert client.get(f'/api/device/plans/{plan}').status_code == 302
    login(client, 'insA')
    assert client.get(f'/api/device/plans/{plan}').status_code == 403


def test_patient_page_exposes_send_control(client, make, people):
    make.plan(people['pat_a'], people['ins_a'])
    login(client, 'patA')
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'id="arduino-send"' in html
    assert 'data-prescription-url="/api/device/plans/0"' in html
