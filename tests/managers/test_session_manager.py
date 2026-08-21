from managers.session_manager import SessionManager


def test_business_session_key_is_isolated_from_regular_user_session():
    manager = SessionManager()
    regular_session = manager.get_or_create_session(456)
    business_session = manager.get_or_create_session(
        "telegram_business:business-123:456"
    )
    other_business_session = manager.get_or_create_session(
        "telegram_business:business-999:456"
    )

    regular_session.data["messages"].append(
        {"role": "user", "content": "regular conversation"}
    )

    assert regular_session.data is not business_session.data
    assert business_session.data is not other_business_session.data
    assert len(business_session.data["messages"]) == 1
    assert business_session.data["messages"][0]["role"] == "developer"
