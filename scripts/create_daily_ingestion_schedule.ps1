param(
    [Parameter(Mandatory = $true)]
    [string]$LambdaArn,
    [Parameter(Mandatory = $true)]
    [string]$ScheduleRoleArn,
    [Parameter(Mandatory = $true)]
    [string]$Region,
    [string]$ScheduleName = "github-issues-rag-daily-ingestion"
)

$target = @{
    Arn     = $LambdaArn
    RoleArn = $ScheduleRoleArn
    Input   = "{}"
} | ConvertTo-Json -Compress

& aws scheduler create-schedule `
    --name $ScheduleName `
    --schedule-expression "cron(0 3 * * ? *)" `
    --schedule-expression-timezone "UTC" `
    --flexible-time-window '{"Mode":"OFF"}' `
    --target $target `
    --state ENABLED `
    --region $Region

if ($LASTEXITCODE -ne 0) {
    throw "Failed to create EventBridge Scheduler schedule."
}
