$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $root 'out\judge-calibrated'
New-Item -ItemType Directory -Force -Path $output | Out-Null

function Read-Submission([string]$relativePath) {
    Get-Content -Raw -LiteralPath (Join-Path $root $relativePath) | ConvertFrom-Json
}

function Write-Submission($submission, [string]$name) {
    $submission | ConvertTo-Json -Depth 8 -Compress | Set-Content -LiteralPath (Join-Path $output $name) -Encoding utf8
}

function Add-ProvenSeeds($baseline, $source, [int]$species, [int]$firstTick, [int]$lastTick, [int]$limit) {
    $added = 0
    foreach ($action in $baseline.actions) {
        if ($action.tick -lt $firstTick -or $action.tick -gt $lastTick -or $added -ge $limit) { continue }
        $sourceAction = $source.actions | Where-Object { $_.tick -eq $action.tick } | Select-Object -First 1
        if (-not $sourceAction) { continue }
        $existing = @{}
        foreach ($plant in $action.plants) { $existing["$($plant.row),$($plant.col)"] = $true }
        $capacity = 20 - @($action.plants).Count
        if ($capacity -le 0) { continue }
        $additions = @($sourceAction.plants | Where-Object {
            $_.plant_index -eq $species -and -not $existing["$($_.row),$($_.col)"]
        } | Select-Object -First ([Math]::Min($capacity, $limit - $added)))
        if ($additions.Count) {
            $action.plants = @($action.plants) + $additions
            $added += $additions.Count
        }
    }
    return $added
}

function Replace-WithProvenSeeds($baseline, $source, [int]$species, [int]$replaceSpecies, [int]$firstTick, [int]$lastTick, [int]$limit) {
    $replaced = 0
    foreach ($action in $baseline.actions) {
        if ($action.tick -lt $firstTick -or $action.tick -gt $lastTick -or $replaced -ge $limit) { continue }
        $sourceAction = $source.actions | Where-Object { $_.tick -eq $action.tick } | Select-Object -First 1
        if (-not $sourceAction) { continue }
        $provenCoordinates = @{}
        foreach ($plant in $sourceAction.plants | Where-Object { $_.plant_index -eq $species }) {
            $provenCoordinates["$($plant.row),$($plant.col)"] = $true
        }
        foreach ($plant in $action.plants) {
            if ($replaced -ge $limit) { break }
            if ($plant.plant_index -eq $replaceSpecies -and $provenCoordinates["$($plant.row),$($plant.col)"]) {
                $plant.plant_index = $species
                $replaced++
            }
        }
    }
    return $replaced
}

function Replace-InConfirmedWindow($baseline, [int]$species, [int]$replaceSpecies, [int]$firstTick, [int]$lastTick, [int]$limit) {
    $replaced = 0
    foreach ($action in $baseline.actions) {
        if ($action.tick -lt $firstTick -or $action.tick -gt $lastTick) { continue }
        foreach ($plant in $action.plants) {
            if ($replaced -ge $limit) { return $replaced }
            if ($plant.plant_index -eq $replaceSpecies) {
                $plant.plant_index = $species
                $replaced++
            }
        }
    }
    return $replaced
}

# L1 stays unchanged until a judge-calibrated density/diversity tradeoff is tested.
Copy-Item -LiteralPath (Join-Path $root 'data\level1_submission.json') -Destination (Join-Path $output 'LEVEL1_PROVEN_222745174.json') -Force

# L2: preserve the 284M baseline and use spare action slots for 20 Orange Blossom
# seeds at ticks where the judge confirmed its unlock. No proven action is removed.
$l2 = Read-Submission 'data\level2_submission.json'
$l2Source = Read-Submission 'out\submissions\LEVEL2_optimized.json'
$l2Added = Add-ProvenSeeds $l2 $l2Source 7 450 499 20
if ($l2Added -eq 0) { $l2Added = Replace-InConfirmedWindow $l2 7 2 450 499 20 }
Write-Submission $l2 'LEVEL2_PROBE_ORANGE_20.json'

# L3: preserve the 209M baseline and add 10 Razorgrass seeds from the judge-
# confirmed 765-768 window, using only spare per-tick capacity.
$l3 = Read-Submission 'data\level3_submission.json'
$l3Source = Read-Submission 'out\submissions\LEVEL3_optimized.json'
$l3Added = Add-ProvenSeeds $l3 $l3Source 19 765 768 10
if ($l3Added -eq 0) { $l3Added = Replace-InConfirmedWindow $l3 19 6 765 768 10 }
Write-Submission $l3 'LEVEL3_PROBE_RAZOR_10.json'

# L4: replace only placements explicitly rejected by the judge for transient
# unlock failures. Dwarf Sunflower is a starter and is underrepresented in the
# final population, so it fills those otherwise empty attempts.
$l4 = Read-Submission 'out\submissions\LEVEL4_optimized.json'
$log = [IO.File]::ReadAllText('C:\Users\modja\Downloads\3b7d703b-7105-4d73-91bf-b3ee67325097-evaluation.log')
$denied = @{}
foreach ($match in [regex]::Matches($log, 'Placement denied for plant (\d+) at \((\d+), (\d+)\): unlock condition check failed')) {
    $denied["$($match.Groups[1].Value),$($match.Groups[2].Value),$($match.Groups[3].Value)"] = $true
}
$l4Replaced = 0
foreach ($action in $l4.actions) {
    foreach ($plant in $action.plants) {
        $key = "$($plant.plant_index),$($plant.row),$($plant.col)"
        if ($denied[$key]) {
            $plant.plant_index = 5
            $l4Replaced++
        }
    }
}
Write-Submission $l4 'LEVEL4_FIX_REJECTED_WITH_SUNFLOWER.json'

[pscustomobject]@{ Level2Added = $l2Added; Level3Added = $l3Added; Level4Replaced = $l4Replaced }
