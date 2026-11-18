from gta6data.models import Vehicle, utcnow


def test_vehicle_roundtrip():
    v = Vehicle(id="test-vehicle", name="Test Vehicle", price=1000, source="unit-test")
    dumped = v.model_dump(mode="json")
    restored = Vehicle.model_validate(dumped)
    assert restored.id == "test-vehicle"
    assert restored.price == 1000
    assert restored.updated_at.tzinfo is not None


def test_vehicle_defaults():
    v = Vehicle(id="x", name="X", source="s")
    assert v.stats == {}
    assert v.updated_at.tzinfo is not None


def test_vehicle_requires_source():
    import pydantic

    try:
        Vehicle(id="x", name="X")
    except pydantic.ValidationError:
        return
    raise AssertionError("Vehicle without source should not validate")
