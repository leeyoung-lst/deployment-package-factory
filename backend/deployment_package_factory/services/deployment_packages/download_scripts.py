from __future__ import annotations

from urllib.parse import quote


def render_download_script(package_id: str, sha256: str, *, shell: str, size: int, etag: str, token: str = "") -> str:
    package_file = f"{package_id}.tar.gz"
    token_query = f"?deployment_package_token={quote(token)}" if token else ""
    download_url = f"./{package_id}/download{token_query}"
    checksum_url = f"./{package_id}/checksum{token_query}"
    if shell == "powershell":
        return _powershell_download_script(package_file, download_url, checksum_url, size, etag)
    return _bash_download_script(package_file, download_url, checksum_url, sha256, size, etag)


def _powershell_download_script(package_file: str, download_url: str, checksum_url: str, size: int, etag: str) -> str:
    checksum_file = f"{package_file}.sha256"
    return "\n".join(
        [
            "# If Windows blocks this unsigned script, run it with:",
            "# powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\<this-file>.ps1",
            "$ErrorActionPreference = 'Stop'",
            f"$PackageFile = '{package_file}'",
            f"$ChecksumFile = '{checksum_file}'",
            f"$DownloadUrl = '{download_url}'",
            f"$ChecksumUrl = '{checksum_url}'",
            f"$PackageSize = [int64]{size}",
            "$PartSize = [int64]67108864",
            f"$ETag = '{etag}'",
            "$PartDir = \"$PackageFile.parts\"",
            "New-Item -ItemType Directory -Force -Path $PartDir | Out-Null",
            "$PartCount = [Math]::Ceiling($PackageSize / $PartSize)",
            "for ($Index = 0; $Index -lt $PartCount; $Index++) {",
            "  $Start = [int64]$Index * $PartSize",
            "  $End = [Math]::Min($Start + $PartSize - 1, $PackageSize - 1)",
            "  $ExpectedLength = $End - $Start + 1",
            "  $PartFile = Join-Path $PartDir ('part{0:D6}' -f ($Index + 1))",
            "  $Existing = if (Test-Path $PartFile) { (Get-Item $PartFile).Length } else { 0 }",
            "  if ($Existing -eq $ExpectedLength) { continue }",
            "  if ($Existing -gt $ExpectedLength) { Remove-Item $PartFile -Force; $Existing = 0 }",
            "  $RangeStart = $Start + $Existing",
            "  $TempFile = \"$PartFile.tmp\"",
            "  curl.exe -fL --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 --speed-time 60 --speed-limit 1024 -H \"If-Range: $ETag\" -H \"Range: bytes=$RangeStart-$End\" -o $TempFile $DownloadUrl",
            "  if ($Existing -gt 0) {",
            "    $InputStream = [System.IO.File]::OpenRead($TempFile)",
            "    try { $OutputStream = [System.IO.File]::Open($PartFile, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write); try { $InputStream.CopyTo($OutputStream) } finally { $OutputStream.Dispose() } } finally { $InputStream.Dispose() }",
            "    Remove-Item $TempFile -Force",
            "  } else { Move-Item -Force $TempFile $PartFile }",
            "}",
            "if (Test-Path $PackageFile) { Remove-Item $PackageFile -Force }",
            "$Out = [System.IO.File]::Open($PackageFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)",
            "try { Get-ChildItem $PartDir -Filter 'part*' | Sort-Object Name | ForEach-Object { $In = [System.IO.File]::OpenRead($_.FullName); try { $In.CopyTo($Out) } finally { $In.Dispose() } } } finally { $Out.Dispose() }",
            "curl.exe -fL --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 -o $ChecksumFile $ChecksumUrl",
            "$Expected = (Get-Content $ChecksumFile -Raw).Trim().Split()[0].ToUpperInvariant()",
            "$Actual = (Get-FileHash $PackageFile -Algorithm SHA256).Hash.ToUpperInvariant()",
            'if ($Actual -ne $Expected) { throw "SHA256 mismatch: expected $Expected actual $Actual" }',
            "Write-Host \"Download verified: $PackageFile\"",
            "",
        ]
    )


def _bash_download_script(package_file: str, download_url: str, checksum_url: str, sha256: str, size: int, etag: str) -> str:
    checksum_file = f"{package_file}.sha256"
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"package_file='{package_file}'",
            f"checksum_file='{checksum_file}'",
            f"download_url='{download_url}'",
            f"checksum_url='{checksum_url}'",
            f"package_size={size}",
            "part_size=67108864",
            f"etag='{etag}'",
            "part_dir=\"$package_file.parts\"",
            "mkdir -p \"$part_dir\"",
            "part_count=$(( (package_size + part_size - 1) / part_size ))",
            "for ((i=0; i<part_count; i++)); do",
            "  start=$((i * part_size))",
            "  end=$((start + part_size - 1))",
            "  if [ \"$end\" -ge \"$package_size\" ]; then end=$((package_size - 1)); fi",
            "  expected_length=$((end - start + 1))",
            "  part_file=$(printf '%s/part%06d' \"$part_dir\" \"$((i + 1))\")",
            "  existing=0",
            "  if [ -f \"$part_file\" ]; then existing=$(wc -c < \"$part_file\"); fi",
            "  if [ \"$existing\" -eq \"$expected_length\" ]; then continue; fi",
            "  if [ \"$existing\" -gt \"$expected_length\" ]; then rm -f \"$part_file\"; existing=0; fi",
            "  range_start=$((start + existing))",
            "  tmp_file=\"$part_file.tmp\"",
            "  curl -fL --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 --speed-time 60 --speed-limit 1024 -H \"If-Range: $etag\" -r \"$range_start-$end\" -o \"$tmp_file\" \"$download_url\"",
            "  cat \"$tmp_file\" >> \"$part_file\"",
            "  rm -f \"$tmp_file\"",
            "done",
            "cat \"$part_dir\"/part* > \"$package_file\"",
            "curl -fL --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 -o \"$checksum_file\" \"$checksum_url\"",
            "expected=$(awk '{print toupper($1)}' \"$checksum_file\")",
            "actual=$(sha256sum \"$package_file\" | awk '{print toupper($1)}')",
            'if [ "$actual" != "$expected" ]; then',
            f"  echo 'SHA256 mismatch. Expected from package metadata: {sha256}' >&2",
            "  echo \"expected $expected actual $actual\" >&2",
            "  exit 1",
            "fi",
            "echo \"Download verified: $package_file\"",
            "",
        ]
    )
