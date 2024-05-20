#!/usr/bin/sh

screen -dmS mon -T xterm sh -c "python mon_rest.py"
screen -dmS conf -T xterm sh -c "python conf_rest.py"
