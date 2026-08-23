from normalize import parse_webhook_payload

TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA_ID",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "PHONE_ID"},
                        "contacts": [{"wa_id": "15551234567", "profile": {"name": "Test"}}],
                        "messages": [
                            {
                                "from": "15551234567",
                                "id": "wamid.HBg1abc123",
                                "timestamp": "1700000000",
                                "type": "text",
                                "text": {"body": "URGENT your account is suspended, click here"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}

IMAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA_ID",
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "15559998888",
                                "id": "wamid.image1",
                                "type": "image",
                                "image": {
                                    "id": "MEDIA_ID_123",
                                    "mime_type": "image/jpeg",
                                    "caption": "is this real?",
                                },
                            }
                        ]
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def test_parse_text_message():
    messages = parse_webhook_payload(TEXT_PAYLOAD)
    assert len(messages) == 1
    m = messages[0]
    assert m.wa_id == "15551234567"
    assert m.msg_type == "text"
    assert "suspended" in m.text_body


def test_parse_image_message():
    messages = parse_webhook_payload(IMAGE_PAYLOAD)
    assert len(messages) == 1
    m = messages[0]
    assert m.msg_type == "image"
    assert m.media_id == "MEDIA_ID_123"
    assert m.media_mime_type == "image/jpeg"
    assert m.text_body == "is this real?"


def test_parse_non_whatsapp_object_returns_empty():
    assert parse_webhook_payload({"object": "page"}) == []


def test_parse_empty_entry_returns_empty():
    assert parse_webhook_payload({"object": "whatsapp_business_account", "entry": []}) == []
