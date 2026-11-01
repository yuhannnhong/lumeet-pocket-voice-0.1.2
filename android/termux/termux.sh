#!/data/data/com.termux/files/usr/bin/sh
# Pocket Voice 手機本地版：在 Termux 裡貼一行就全部裝好
set -e
BASE=https://pub-10ca59f0823f4734a9938c42076890d3.r2.dev/v1
echo "== 更新 Termux"
yes | pkg update
yes | pkg upgrade -o Dpkg::Options::=--force-confnew
pkg install -y proot-distro
echo "== 安裝 Ubuntu"
proot-distro list 2>/dev/null | grep -q "ubuntu.*installed" || proot-distro install ubuntu || true
echo "== 安裝 Pocket Voice"
proot-distro login ubuntu -- sh -c "apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates && curl -fsSL $BASE/setup.sh | sh"
# 之後啟動只要打：pv 密碼
cat > $PREFIX/bin/pv <<'EOS'
#!/data/data/com.termux/files/usr/bin/sh
[ -n "$1" ] || { echo "用法：pv 你的密碼"; exit 1; }
termux-wake-lock 2>/dev/null || true
exec proot-distro login ubuntu -- sh /root/pv/pocket-voice/run.sh "$1"
EOS
chmod +x $PREFIX/bin/pv
echo
echo "全部裝好了！以後啟動只要打：pv 你的密碼"
