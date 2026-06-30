import { downloadDeploymentPackage, downloadDeploymentPackageChecksum } from "../../api/deploymentPackages";

export function resumeDownloadCommand(packageId: string) {
  const filename = `${packageId}.tar.gz`;
  const url = downloadDeploymentPackage(packageId);
  const checksumUrl = downloadDeploymentPackageChecksum(packageId);
  const script = [
    `$pkg = "${filename}"`,
    `$sum = "${filename}.sha256"`,
    `curl.exe -fL -C - --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 --speed-time 60 --speed-limit 1024 -o $pkg "${url}"`,
    `curl.exe -fL --retry 20 --retry-delay 3 --retry-all-errors --connect-timeout 15 -o $sum "${checksumUrl}"`,
    `$expected = (Get-Content $sum -Raw).Trim().Split()[0].ToUpperInvariant()`,
    `$actual = (Get-FileHash $pkg -Algorithm SHA256).Hash.ToUpperInvariant()`,
    `if ($actual -ne $expected) { throw "SHA256 mismatch: expected $expected actual $actual" }`,
  ].join("\n");
  return `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ${JSON.stringify(script)}`;
}
