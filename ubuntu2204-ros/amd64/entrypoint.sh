#!/bin/bash
# Generated copies are self-contained. Edit this template, then run scripts/generate.py.
set -Eeuo pipefail

die() { echo "entrypoint: $*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || die 'Start as root; the entrypoint drops privileges after initialization.'
USER=${USER:-ubuntu}
PASSWORD=${PASSWORD:-ubuntu}
[[ $USER =~ ^[a-z_][a-z0-9_-]{0,31}$ && $USER != root ]] || die 'USER must be a valid non-root Linux username.'
[[ $PASSWORD != *$'\n'* && $PASSWORD != *$'\r'* ]] || die 'PASSWORD must not contain newlines.'

if ! id "$USER" >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash --user-group "$USER"
fi
[[ $(id -u "$USER") != 0 ]] || die 'USER must not have UID 0.'
usermod --append --groups sudo "$USER"
export HOME
HOME=$(getent passwd "$USER" | cut -d: -f6)
[[ $HOME == /home/"$USER" ]] || die 'Existing USER must have /home/USER as its home.'
mkdir -p "$HOME"
# Populate a newly mounted empty home without replacing existing user files.
cp -an /etc/skel/. "$HOME/"
chown "$USER:$(id -gn "$USER")" "$HOME"
for config in .bashrc .profile .bash_logout; do
    [[ ! -f $HOME/$config ]] || chown "$USER:$(id -gn "$USER")" "$HOME/$config"
done
printf '%s:%s\n' "$USER" "$PASSWORD" | chpasswd
export USER LOGNAME="$USER" SHELL=/bin/bash
umask 022
mkdir -p /run/sshd
ssh-keygen -A >/dev/null

if [[ -f /etc/profile.d/ros.sh ]]; then
    # ROS setup scripts are not nounset-safe.
    set +u
    source /etc/profile.d/ros.sh
    set -u
fi

if [[ ${1:-services} != services ]]; then
    unset PASSWORD VNC_PASSWORD
    cd "$HOME"
    exec gosu "$USER" "$@"
fi

if [[ ${IMAGE_DESKTOP:-0} != 1 ]]; then
    unset PASSWORD VNC_PASSWORD
    exec /usr/sbin/sshd -D -e
fi

VNC_PASSWORD=${VNC_PASSWORD:-$PASSWORD}
VNC_GEOMETRY=${VNC_GEOMETRY:-1920x1080}
[[ $VNC_PASSWORD != *$'\n'* && $VNC_PASSWORD != *$'\r'* ]] || die 'VNC_PASSWORD must not contain newlines.'
[[ $VNC_GEOMETRY =~ ^[1-9][0-9]{2,4}x[1-9][0-9]{2,4}$ ]] || die 'VNC_GEOMETRY must look like 1920x1080.'
export DISPLAY=:1 VNC_GEOMETRY
install -d -m 700 -o "$USER" -g "$(id -gn "$USER")" "$HOME/.vnc"
printf '%s\n' "$VNC_PASSWORD" | tigervncpasswd -f > "$HOME/.vnc/passwd"
chmod 600 "$HOME/.vnc/passwd"
chown "$USER:$(id -gn "$USER")" "$HOME/.vnc/passwd"
cat > "$HOME/.vnc/xstartup" <<'XSTARTUP'
#!/bin/bash
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=MATE DESKTOP_SESSION=mate
[[ ! -f /etc/profile.d/ros.sh ]] || source /etc/profile.d/ros.sh
exec dbus-run-session -- mate-session
XSTARTUP
chmod 755 "$HOME/.vnc/xstartup"
chown "$USER:$(id -gn "$USER")" "$HOME/.vnc/xstartup"
install -d -m 700 -o "$USER" -g "$(id -gn "$USER")" "/run/user/$(id -u "$USER")"
export XDG_RUNTIME_DIR="/run/user/$(id -u "$USER")"
mkdir -p /run/dbus
dbus-uuidgen --ensure=/etc/machine-id
# Container restarts can leave stale locks on the writable layer.
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "$HOME"/.vnc/*:1.pid /run/dbus/pid
cat > /run/ubuntu-dev-supervisor.conf <<CONF
[unix_http_server]
file=/run/ubuntu-dev-supervisor.sock
chmod=0700
[supervisord]
nodaemon=true
user=root
logfile=/dev/null
pidfile=/run/ubuntu-dev-supervisord.pid
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[supervisorctl]
serverurl=unix:///run/ubuntu-dev-supervisor.sock
[program:dbus]
command=/usr/bin/dbus-daemon --system --nofork --nopidfile
priority=10
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
[program:ssh]
command=/usr/sbin/sshd -D -e
priority=20
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
[program:vnc]
command=/usr/sbin/gosu $USER /usr/bin/tigervncserver :1 -fg -localhost -SecurityTypes VncAuth -geometry $VNC_GEOMETRY -depth 24 -rfbauth $HOME/.vnc/passwd -xstartup $HOME/.vnc/xstartup
priority=30
autorestart=true
stopasgroup=true
killasgroup=true
stopwaitsecs=10
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
[program:novnc]
command=/usr/bin/websockify --web=/usr/share/novnc 80 127.0.0.1:5901
priority=40
autorestart=true
stopasgroup=true
killasgroup=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
CONF
unset PASSWORD VNC_PASSWORD
exec /usr/bin/supervisord -c /run/ubuntu-dev-supervisor.conf
