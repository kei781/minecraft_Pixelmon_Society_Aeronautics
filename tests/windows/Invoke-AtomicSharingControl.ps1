param(
    [Parameter(Mandatory = $true)][string]$Java,
    [Parameter(Mandatory = $true)][string]$WriterJar,
    [Parameter(Mandatory = $true)][string]$FixtureRoot,
    [ValidateRange(20, 10000)][int]$Iterations = 200
)

$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $FixtureRoot) { throw 'A new owned fixture directory is required.' }
$null = New-Item -ItemType Directory -Path $FixtureRoot
$fixturePath = [IO.Path]::GetFullPath($FixtureRoot)
$encoding = [Text.UTF8Encoding]::new($false)
$results = @()
foreach ($mode in @('Read', 'ReadWriteDelete')) {
    $folder = Join-Path $fixturePath $mode
    $null = New-Item -ItemType Directory -Path $folder
    [IO.File]::WriteAllText((Join-Path $folder '.psa-file-share-test'), 'psa-atomic-share-fixture-v1', $encoding)
    [IO.File]::WriteAllText((Join-Path $folder 'checkpoint.json'), '{"fixture":true}', $encoding)
    $readerJob = Start-Job -ArgumentList $folder, $mode -ScriptBlock {
        param($Folder, $Mode)
        $ErrorActionPreference = 'Stop'
        $share = [IO.FileShare]::Read
        if ($Mode -eq 'ReadWriteDelete') { $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete }
        $reads = 0
        $readFailures = 0
        $until = [DateTime]::UtcNow.AddSeconds(45)
        while ([DateTime]::UtcNow -lt $until -and !(Test-Path -LiteralPath (Join-Path $Folder 'writer-finished.signal'))) {
            $stream = $null
            $text = $null
            try {
                $stream = [IO.FileStream]::new((Join-Path $Folder 'checkpoint.json'), [IO.FileMode]::Open, [IO.FileAccess]::Read, $share)
                [IO.File]::WriteAllText((Join-Path $Folder 'reader-open.signal'), 'ready')
                $text = [IO.StreamReader]::new($stream)
                $null = $text.ReadToEnd() | ConvertFrom-Json
                $reads++
                Start-Sleep -Milliseconds 5
            } catch [IO.IOException] { $readFailures++ }
            finally {
                if ($null -ne $text) { $text.Dispose() }
                elseif ($null -ne $stream) { $stream.Dispose() }
            }
        }
        [PSCustomObject]@{ reads = $reads; read_failures = $readFailures }
    }
    try {
        $writerOutput = & $Java '-cp' $WriterJar 'AtomicCheckpointWriter' $folder "$Iterations"
        if ($LASTEXITCODE -ne 0) { throw "Fixture Java producer failed: $LASTEXITCODE" }
        $writer = ($writerOutput -join "`n") | ConvertFrom-Json
        $null = Wait-Job -Job $readerJob -Timeout 50
        if ($readerJob.State -ne 'Completed') { throw "Fixture reader did not complete: $($readerJob.State)" }
        $readerResult = Receive-Job -Job $readerJob -ErrorAction Stop
        if ($readerResult.reads -lt 1) { throw 'Reader never observed the fixture.' }
        $results += [PSCustomObject]@{ sharing = $mode; writer = $writer; reader = $readerResult }
    } finally {
        if ($readerJob.State -in @('Running', 'NotStarted')) { Stop-Job -Job $readerJob }
        Remove-Job -Job $readerJob
    }
}
$baseline = @($results | Where-Object { $_.sharing -eq 'Read' })[0]
$deleteShared = @($results | Where-Object { $_.sharing -eq 'ReadWriteDelete' })[0]
$report = [ordered]@{
    fixture = $true
    game_files_used = $false
    baseline_reproduced = ($baseline.writer.failed -gt 0)
    delete_shared_all_writes_succeeded = ($deleteShared.writer.failed -eq 0 -and $deleteShared.writer.successful -eq $Iterations)
    results = $results
    scope = 'Measure both sharing modes; success with Delete sharing is a hypothesis, not a preset verdict.'
}
[IO.File]::WriteAllText((Join-Path $fixturePath 'result.json'), ($report | ConvertTo-Json -Depth 10), $encoding)
$report | ConvertTo-Json -Depth 10
