@echo off
if not exist logs mkdir logs
wscript "%~dp0start.vbs"
