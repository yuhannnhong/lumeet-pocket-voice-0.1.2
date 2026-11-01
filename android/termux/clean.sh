#!/bin/sh
# 已經裝好的人用：清掉安裝時留下的暫存，不影響 Pocket Voice。在 Termux 貼：
#   proot-distro login ubuntu -- sh -c "curl -fsSL https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1/clean.sh | sh"
before=$(du -sm / 2>/dev/null | cut -f1)
apt-get clean
rm -rf /var/lib/apt/lists/* /root/.cache/pip /tmp/*
find /root/pv -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
after=$(du -sm / 2>/dev/null | cut -f1)
echo "清好了：省下大約 $((before - after)) MB"
