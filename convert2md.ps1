# Получаем путь к файлу, который передал Explorer
param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

# Путь к твоему проекту
$projectPath = "D:\work\file2x"

# Активируем venv
$venvPath = Join-Path $projectPath ".venv\Scripts\Activate.ps1"
. $venvPath

# Запускаем конвертацию
python "$projectPath\cli.py" "$FilePath" --to md
pause