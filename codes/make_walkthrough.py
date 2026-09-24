"""Add the guide narration to a single continuous screen recording.

No splices, slide frames, speed changes, transitions, or composited interfaces.
Only a fixed crop removes browser chrome/padding, plus a leading trim and audio.
The native variable-frame-rate stream is encoded at 30 fps for compatibility.
"""
from pathlib import Path
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True)
    p.add_argument('--start',type=float,default=2);p.add_argument('--seconds',type=float,default=149)
    p.add_argument('--audio',type=Path,default=ROOT/'dist/dna_guide_narration.wav')
    p.add_argument('--name',default='dna_walkthrough');a=p.parse_args()
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    silent=out/(a.name+'_silent.mp4');narrated=out/(a.name+'_narrated.mp4')
    cmd=['ffmpeg','-y','-loglevel','error','-ss',str(a.start),'-i',str(a.video),'-an','-vf','crop=3456:1812:0:356,tpad=stop_mode=clone:stop_duration=2','-t',str(a.seconds),'-r','30','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)]
    subprocess.run(cmd,check=True)
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(silent),'-i',str(a.audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(a.seconds),'-movflags','+faststart',str(narrated)],check=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,r_frame_rate,nb_frames','-show_entries','format=duration,size','-of','json',str(narrated)]))
    meta=dict(kind='Continuous recording of the running application in a dedicated Chrome window',video=str(narrated.relative_to(ROOT)),silent_master=str(silent.relative_to(ROOT)),source=str(a.video),synthetic_guide_voice='macOS Samantha; intended for replacement with author narration',editing=['Fixed spatial crop to application content','Trim lead-in and ending','Mux separately timed narration','Encode at 30 fps; hold unchanged final screen if needed'],source_scene_cuts=0,seconds=a.seconds,probe=info)
    (ROOT/'results'/f'{a.name}.json').write_text(json.dumps(meta,indent=2))
    print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
