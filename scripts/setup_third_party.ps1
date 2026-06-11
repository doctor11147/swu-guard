$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Clone-Pinned($Url, $Dir, $Revision) {
    $Path = Join-Path $Root $Dir
    if (-not (Test-Path (Join-Path $Path ".git"))) {
        git clone $Url $Path
    }
    git -C $Path fetch --tags --prune
    git -C $Path checkout --detach $Revision
}

Clone-Pinned "https://github.com/otroshi/edgeface.git" "edgeface" "ce86851cfc37979a9cd2558598d0e9bc592cbba3"
Clone-Pinned "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git" "Silent-Face-Anti-Spoofing" "b6d5f04ad78778917853b25c778acef6d5626d15"

Write-Host "Third-party source trees are ready and ignored by Git."
Write-Host "Review THIRD_PARTY_NOTICES.md and MODEL_MANIFEST.md before use."
