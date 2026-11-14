"""Use the established workstation Windows SSH -> WSL route."""
import argparse
import base64
from pathlib import Path
import subprocess

def main():
    p=argparse.ArgumentParser()
    p.add_argument('script',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.script.suffix=='.ps1':
        payload=base64.b64encode(a.script.read_text(encoding='utf-8').encode('utf-16le')).decode()
        remote='powershell -NoProfile -NonInteractive -EncodedCommand '+payload
    else:
        payload=base64.b64encode(a.script.read_bytes()).decode()
        remote=('wsl -d Ubuntu-22.04 -u root -e bash -lc '
                '"echo '+payload+' | base64 -d | bash"')
    result=subprocess.run(['wsl','-d','Ubuntu-22.04','-u','ty','--','ssh','-p','22',
        '-i','/home/ty/.ssh/id_5090','-o','IdentitiesOnly=yes','-o','BatchMode=yes',
        '-o','ConnectTimeout=15','Administrator@192.168.10.100',remote],
        stdout=subprocess.PIPE if a.output else None)
    if a.output:
        assert not a.output.exists(), 'Do not overwrite a saved snapshot'
        a.output.write_bytes(result.stdout)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
