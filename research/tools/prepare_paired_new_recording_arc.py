"""Re-propose the visible upper arc, excluding long support-scatter tails; review only."""
from prepare_paired_resplit_additions import *
import cv2
DEST=ROOT/'DataSet/paired_new_recording_arc_review'
def main():
    DEST.mkdir(exist_ok=False)
    rec='2023-09-20_174711';pool=[r for r in read(ROOT/'DataSet/paired_more_recordings_review_verified/manifest.json') if r['recording']==rec]
    take=[pool[round(i*(len(pool)-1)/39)] for i in range(40)];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);sheets=[]
    for j,r in enumerate(take):
        a=raw_array(r['sonar_source']);sm=cv2.GaussianBlur(a.astype(np.float32),(3,5),0)
        roi=sm[120:310];ys=np.argmax(roi,axis=0)+120
        strengths=roi.max(axis=0);valid=strengths>max(35,float(np.percentile(strengths,90))*.35)
        xx=np.flatnonzero(valid);assert len(xx)>30
        box=[max(0,int(xx.min())-2),max(0,int(ys[valid].min())-5),min(128,int(xx.max())+3),min(a.shape[0],int(ys[valid].max())+35)]
        r.update(ordinal=j,proposal_xyxy=box,decision='unreviewed',proposal_method='upper primary arc ridge + margins; re-review required; no old proposal acceptance')
        if j%20==0:
            canvas=Image.new('RGB',(1800,2285),'#f4f6fa');d=ImageDraw.Draw(canvas);d.text((5,4),rec+' | corrected SD / re-proposed SONAR primary arc | NOT accepted',font=font,fill='black')
        x=j%20%4*450;y=30+j%20//4*450;d.text((x+3,y),f'{j} f{r["frame"]} {box}',font=font,fill='black')
        im=Image.open(r['camera_source']).convert('RGB');ImageDraw.Draw(im).rectangle(r['camera_boxes_xyxy'][0],outline='#00ff40',width=2);canvas.paste(im.resize((446,251)),(x,y+22))
        son=Image.fromarray(np.clip(a.astype(float)*2.5,0,255).astype(np.uint8)).convert('RGB');ImageDraw.Draw(son).rectangle(box,outline='#00ff40',width=1)
        canvas.paste(son.resize((108,165)),(x,y+280));canvas.paste(son.crop((0,max(0,box[1]-25),128,min(son.height,box[3]+25))).resize((334,165)),(x+112,y+280))
        r['sheet']=f'page-{j//20:02d}.jpg'
        if j%20==19:
            p=DEST/r['sheet'];canvas.save(p,quality=96);sheets.append(dict(path=p.name,sha256=sha(p)))
    save(DEST/'proposals.json',take);save(DEST/'sheets.json',sheets)
    print(dict(proposals=len(take),accepted_new_pairs=0))
if __name__=='__main__':main()
