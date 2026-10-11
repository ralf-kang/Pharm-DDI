@echo off
chcp 65001 > nul
echo ====================================================================
echo  [Pharm-DDI Expert Suite] 온프라미스 약학 전문가 시스템 구동기
echo ====================================================================
echo.

:: Python 3.11 또는 기본 py 런처 감지
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Python Launcher(py -3.11)를 사용하여 온프라미스 서버를 시작합니다...
    py -3.11 server.py
    goto end
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] 시스템 Python을 사용하여 온프라미스 서버를 시작합니다...
    python server.py
    goto end
)

echo [ERROR] 파이썬 실행기를 찾을 수 없습니다. 파이썬이 설치되어 있는지 확인해주세요.
pause

:end

