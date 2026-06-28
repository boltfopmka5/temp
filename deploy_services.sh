#!/bin/bash

# ============================================================
# FOREX SIGNAL SERVER - НАСТРОЙКА СЕРВИСОВ
# ============================================================
# Запуск: chmod +x deploy_services.sh && ./deploy_services.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 НАСТРОЙКА СЕРВИСОВ И NGINX"
echo "=========================================="

# ============================================================
# 1. СОЗДАНИЕ SYSTEMD СЕРВИСОВ
# ============================================================
echo ""
echo "⚙️ СОЗДАНИЕ SYSTEMD СЕРВИСОВ..."

# PO-API (порт 5000)
cat > /etc/systemd/system/forex-po.service << 'EOF'
[Unit]
Description=Forex PO API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/deploy/site
ExecStart=/deploy/venv/bin/python /deploy/site/po_api_backend_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# FCS-API (порт 5001)
cat > /etc/systemd/system/forex-fcs.service << 'EOF'
[Unit]
Description=Forex FCS API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/deploy/site-fcs
ExecStart=/deploy/venv/bin/python /deploy/site-fcs/backend_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Боты (TG + VK)
cat > /etc/systemd/system/forex-bots.service << 'EOF'
[Unit]
Description=Forex Bots TG+VK
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/deploy
ExecStart=/deploy/venv/bin/python /deploy/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ СЕРВИСЫ СОЗДАНЫ"

# ============================================================
# 2. ЗАПУСК СЕРВИСОВ
# ============================================================
echo ""
echo "▶️ ЗАПУСК СЕРВИСОВ..."

systemctl daemon-reload
systemctl enable forex-po forex-fcs forex-bots
systemctl start forex-po forex-fcs forex-bots

echo "✅ СЕРВИСЫ ЗАПУЩЕНЫ"

# ============================================================
# 3. НАСТРОЙКА NGINX
# ============================================================
echo ""
echo "🌐 НАСТРОЙКА NGINX..."

cat > /etc/nginx/sites-available/forex << 'EOF'
server {
    listen 80;
    server_name _;

    location /po {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /fcs {
        proxy_pass http://127.0.0.1:5001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -sf /etc/nginx/sites-available/forex /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl reload nginx

echo "✅ NGINX НАСТРОЕН"

# ============================================================
# 4. ОТКРЫТИЕ ПОРТОВ
# ============================================================
echo ""
echo "🔓 ОТКРЫТИЕ ПОРТОВ..."

ufw allow 22/tcp 2>/dev/null || true
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
echo "y" | ufw enable 2>/dev/null || true

echo "✅ ПОРТЫ ОТКРЫТЫ"

# ============================================================
# 5. ПРОВЕРКА
# ============================================================
echo ""
echo "🔍 ПРОВЕРКА РАБОТЫ..."

sleep 3

echo ""
echo "📊 СТАТУС СЕРВИСОВ:"
systemctl status forex-po --no-pager | grep -E "Active|loaded"
systemctl status forex-fcs --no-pager | grep -E "Active|loaded"
systemctl status forex-bots --no-pager | grep -E "Active|loaded"
systemctl status nginx --no-pager | grep -E "Active|loaded"

echo ""
echo "🌐 ПРОВЕРКА API:"
echo -n "PO-API:  "
curl -s http://localhost:5000/api/health || echo "❌ ОШИБКА"
echo -n "FCS-API: "
curl -s http://localhost:5001/api/health || echo "❌ ОШИБКА"
echo ""

# ============================================================
# 6. ВЫВОД ИНФОРМАЦИИ
# ============================================================
IP=$(curl -s ifconfig.me 2>/dev/null || echo "IP_НЕ_ОПРЕДЕЛЁН")

echo ""
echo "=========================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА!"
echo "=========================================="
echo ""
echo "📱 ДОСТУП К САЙТАМ:"
echo "   PO-API:  http://$IP/po"
echo "   FCS-API: http://$IP/fcs"
echo ""
echo "📋 ПОЛЕЗНЫЕ КОМАНДЫ:"
echo "   Логи PO:  journalctl -u forex-po -f"
echo "   Логи FCS: journalctl -u forex-fcs -f"
echo "   Логи ботов: journalctl -u forex-bots -f"
echo ""
echo "🔄 ПЕРЕЗАПУСК ВСЕГО:"
echo "   systemctl restart forex-po forex-fcs forex-bots nginx"
echo ""
echo "=========================================="
