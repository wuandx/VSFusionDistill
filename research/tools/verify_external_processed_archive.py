"""Stream-check the existing external archive without extracting it."""
import hashlib,json,time
from pathlib import Path
SOURCE=Path('/mnt/uxo_external_ro/datasets/uxo-dataset2024/data_processed.7z')
OUT=Path('/mnt/d/agent_workspace/水下/声呐目标检测_workflow/related_work/uxo/external-archive-verification.json')
EXPECTED='2b9ef16c763a6964c608ed99a9cd1edb'
SIZE=61513277947
def save(data):
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(OUT)
def main():
    start=time.time();h=hashlib.md5();done=0;last=0
    assert SOURCE.stat().st_size==SIZE
    with SOURCE.open('rb',buffering=0) as f:
        while data:=f.read(16*1024*1024):
            h.update(data);done+=len(data)
            if time.time()-last>=30:
                save({'status':'hashing','source':str(SOURCE),'bytes_read':done,'expected_size':SIZE,'elapsed_seconds':round(time.time()-start,1),'expected_md5':EXPECTED,'mount':'btrfs ro,rescue=nologreplay'})
                print(f'{done}/{SIZE} bytes checked',flush=True);last=time.time()
    actual=h.hexdigest();result={'status':'verified' if actual==EXPECTED else 'checksum_mismatch','source':str(SOURCE),'size_bytes':done,'expected_size':SIZE,'md5':actual,'expected_md5':EXPECTED,'matches':actual==EXPECTED,'elapsed_seconds':round(time.time()-start,1),'extracted':False,'mount':'btrfs ro,rescue=nologreplay'}
    save(result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
