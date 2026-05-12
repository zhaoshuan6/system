#!/bin/bash
mkdir -p tests/results
echo "=========================================="
echo "请确保Flask服务已在5000端口运行"
echo "如未启动，请先运行: python app.py"
echo "=========================================="
read -p "Flask服务已启动？按回车继续..."

echo ""
echo "开始运行功能测试..."
pytest tests/test_01_auth.py \
       tests/test_02_video.py \
       tests/test_03_search.py \
       tests/test_04_trajectory.py \
       tests/test_05_monitor.py \
       tests/test_06_history.py \
       -v --tb=short \
       --html=tests/results/functional_report.html \
       --self-contained-html

echo ""
echo "开始运行性能测试..."
pytest tests/test_07_performance.py \
       -v --tb=short \
       --html=tests/results/performance_report.html \
       --self-contained-html

echo ""
echo "全部完成！报告位置："
echo "  功能测试: tests/results/functional_report.html"
echo "  性能测试: tests/results/performance_report.html"
echo "  性能数据: tests/results/*.json"
