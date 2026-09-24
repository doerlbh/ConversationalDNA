"""Generate a replaceable guide-voice track and timestamped author reading script."""
from pathlib import Path
import argparse,json,subprocess,wave
from walkthrough_script import SEGMENTS,FULL_SEGMENTS
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'qa/narration';OUT.mkdir(exist_ok=True)
RATE=48000;TOTAL=149

def run(args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    segments=FULL_SEGMENTS if args.full else SEGMENTS
    total=219 if args.full else TOTAL
    stem='FULL_READING_SCRIPT' if args.full else 'READING_SCRIPT'
    audio_name='dna_full_guide_narration.wav' if args.full else 'dna_guide_narration.wav'
    track=bytearray(RATE*2*total);meta=[]
    reading=['# Conversational DNA — author reading script','',
      '**For Baihan Lin.** The supplied guide audio uses macOS Samantha, not Baihan’s voice. Read only the paragraphs aloud; headings are timing cues. The accompanying video is a continuous recording of the running application.','',
      f'{total}-second '+('full-function tour (not the conference upload).' if args.full else 'conference walkthrough.')+' The timestamps identify when each paragraph starts. Natural short pauses are included before the next section.','']
    plain=[]
    for i,(start,stop,title,words) in enumerate(segments):
        text=OUT/f'{i:02}.txt';text.write_text(words)
        rate=165
        while True:
            aiff=OUT/f'{i:02}.aiff';wav=OUT/f'{i:02}.wav'
            run(['/usr/bin/say','-v','Samantha','-r',str(rate),'-f',str(text),'-o',str(aiff)])
            run(['ffmpeg','-y','-loglevel','error','-i',str(aiff),'-ar',str(RATE),'-ac','1','-c:a','pcm_s16le',str(wav)])
            with wave.open(str(wav),'rb') as w: duration=w.getnframes()/RATE;pcm=w.readframes(w.getnframes())
            if duration<=stop-start-.3:break
            rate+=3
            if rate>210:raise ValueError((title,duration,stop-start))
        a=int(start*RATE*2);track[a:a+len(pcm)]=pcm
        reading+= [f'## {int(start)//60:02}:{int(start)%60:02}–{int(stop)//60:02}:{int(stop)%60:02} · {title}','',words,'']
        plain.append(words);meta.append(dict(start=start,stop=stop,title=title,narration=words,spoken_seconds=duration,voice_rate=rate))
        print(title,round(duration,2),'seconds at',rate,'wpm',flush=True)
    with wave.open(str(ROOT/'dist'/audio_name),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(RATE);w.writeframes(track)
    (ROOT/'docs'/(stem+'.md')).write_text('\n'.join(reading))
    (ROOT/'docs'/(stem+'.txt')).write_text('\n\n'.join(plain)+'\n')
    (ROOT/'results'/('full_narration_timing.json' if args.full else 'narration_timing.json')).write_text(json.dumps(dict(duration=total,voice='macOS Samantha; temporary synthetic guide voice',segments=meta),indent=2))
if __name__=='__main__':main()
