@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" || exit /b 1
set "PGROOT=C:\Program Files\PostgreSQL\16"
echo PGROOT=%PGROOT%
cd /d C:\Users\ADMINI~1\AppData\Local\Temp\pgvector || exit /b 1
nmake /F Makefile.win clean
nmake /F Makefile.win || exit /b 1
nmake /F Makefile.win install || exit /b 1
echo BUILD_AND_INSTALL_OK
