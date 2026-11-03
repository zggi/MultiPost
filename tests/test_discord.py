import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.captions import adapt  # noqa: E402
from multipost.models import Account, Job  # noqa: E402
from multipost.publishers import discord_webhook as d  # noqa: E402

HOOK = "https://discord.com/api/webhooks/123/abc"


class FakeResp:
    def __init__(self, status, body=""):
        self.status_code = status
        self.text = body
        self._body = body

    def json(self):
        import json
        return json.loads(self._body) if self._body else {}


def _publish(monkey_status=204, monkey_body="", file_size=100):
    calls = {}

    def fake_post(url, data=None, files=None, proxies=None, timeout=None):
        calls["url"] = url
        calls["content"] = data.get("content") if data else None
        calls["file_name"] = files["file"][0] if files else None
        return FakeResp(monkey_status, monkey_body)

    orig_post = d.requests.post
    orig_getsize = os.path.getsize
    d.requests.post = fake_post
    os.path.getsize = lambda p: file_size
    try:
        acc = Account(platform="discord", label="Server", mode="webhook",
                      secret=HOOK)
        job = Job(video_path="/tmp/v.mp4", caption="halo", account_ids=[acc.id])
        job.video_path = os.path.abspath(__file__)
        res = d.publish(acc, job, "halo")
    finally:
        d.requests.post = orig_post
        os.path.getsize = orig_getsize
    return res, calls


def test_adapt_discord_truncates_to_2000():
    ad = adapt("discord", "x" * 2500)
    assert len(ad.text) == 2000
    assert ad.warnings


def test_publish_success_posts_file_and_caption():
    res, calls = _publish()
    assert res.status == "success"
    assert calls["url"] == HOOK
    assert calls["content"] == "halo"
    assert calls["file_name"] == os.path.basename(os.path.abspath(__file__))


def test_publish_rejects_non_webhook_url():
    acc = Account(platform="discord", label="Server", mode="webhook",
                  secret="https://example.com/hook")
    job = Job(video_path="/tmp/v.mp4", caption="halo", account_ids=[acc.id])
    res = d.publish(acc, job, "halo")
    assert res.status == "failed"
    assert "webhook" in res.message.lower()


def test_publish_rejects_oversize_file():
    res, _ = _publish(file_size=26 * 1024 * 1024)
    assert res.status == "failed"
    assert "25 MB" in res.message


def test_publish_surfaces_discord_error():
    res, _ = _publish(monkey_status=404,
                      monkey_body='{"message": "Unknown Webhook"}')
    assert res.status == "failed"
    assert "Unknown Webhook" in res.message
