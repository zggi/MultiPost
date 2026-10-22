import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multipost.captions import adapt  # noqa: E402


def test_threads_truncates_at_500_with_warning():
    out = adapt("threads", "halo " * 200)
    assert len(out.text) <= 500
    assert out.text.endswith("…")
    assert out.warnings, "truncation must be reported, never silent"


def test_instagram_short_caption_untouched():
    out = adapt("instagram", "Warung rame pagi ini. Kamu tim 1/2/3? #kasir")
    assert out.text.startswith("Warung rame")
    assert not out.warnings


def test_youtube_title_from_first_line_and_limit():
    caption = "Judul " + "panjang " * 30 + "\nDeskripsi lengkap di sini."
    out = adapt("youtube", caption)
    assert len(out.title) <= 100
    assert "Deskripsi lengkap" in out.text


def test_youtube_explicit_title_wins():
    out = adapt("youtube", "isi deskripsi", title="Judul Pilihan Saya")
    assert out.title == "Judul Pilihan Saya"
