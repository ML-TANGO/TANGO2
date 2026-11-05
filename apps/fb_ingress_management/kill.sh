#!/bin/bash
ps -ef | grep run | grep -v 'grep' | awk '{print $2}' | xargs -I {} kill -9 {}
ps -ef | grep uvicorn | grep -v 'grep' | awk '{print $2}' | xargs -I {} kill -9 {}
/app/run.sh