"""Publication figures from recorded measurements and actual browser capture."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
import numpy as np

ROOT=Path(__file__).resolve().parents[1];FIG=ROOT/'figures';RES=ROOT/'results'
# Register the actual Times New Roman face, rather than a generic serif alias.
font_path=Path('/System/Library/Fonts/Supplemental/Times New Roman.ttf')
if font_path.exists(): font_manager.fontManager.addfont(str(font_path))
plt.rcParams.update({'font.family':'Times New Roman','font.size':9,'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
TEAL='#23685a';PURPLE='#8663a7';INK='#17252a';GRAY='#737e79';PAPER='#f6f7f1'

def main():
    metrics=json.loads((RES/'retrieval_metrics.json').read_text());dense=json.loads((RES/'dense_metrics.json').read_text())
    fig,ax=plt.subplots(figsize=(6.7,2.25));names=['TF–IDF','MiniLM','Sequence + speaker','+ Target correspondence'];keys=['tfidf','dense','sequence','graph'];vals=[];lo=[];hi=[]
    for k in keys:
        v=dense['metrics']['p5'] if k=='dense' else metrics['methods'][k]['p5'];m=v['mean'];vals.append(m);lo.append(m-v['ci95'][0]);hi.append(v['ci95'][1]-m)
    bars=ax.barh(np.arange(4),vals,color=['#b6c2ba','#b6c2ba',PURPLE,TEAL],height=.55,xerr=[lo,hi],error_kw={'elinewidth':1,'capsize':2,'ecolor':INK})
    ax.set_yticks(np.arange(4),names);ax.invert_yaxis();ax.set_xlim(0,1);ax.set_xlabel('Precision@5 on exact annotated motif containment');ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1));ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    for b,v in zip(bars,vals):ax.text(max(v+.045,.07),b.get_y()+b.get_height()/2,f'{v*100:.1f}%',va='center',fontsize=9,color=INK)
    fig.tight_layout();fig.savefig(FIG/'retrieval.pdf',bbox_inches='tight');fig.savefig(FIG/'retrieval.png',dpi=600,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.7,.60));ax.set_xlim(0,10);ax.set_ylim(0,1);ax.axis('off')
    from matplotlib.patches import Rectangle
    labels=['Corpus adapters','Episode index','Local alignment','Interactive atlas','Evidence export']
    for i,label in enumerate(labels):
        x=i*2.05
        ax.add_patch(Rectangle((x,.20),1.72,.58,facecolor='white',edgecolor='black',linewidth=.7))
        ax.text(x+.86,.49,label,ha='center',va='center',fontfamily='Times New Roman',fontsize=8,fontweight='normal',color='black')
        if i<4:ax.annotate('',xy=(x+2.04,.49),xytext=(x+1.74,.49),arrowprops=dict(arrowstyle='->',color='black',lw=.7))
    fig.subplots_adjust(left=0,right=1,top=1,bottom=0);fig.savefig(FIG/'architecture.pdf',bbox_inches='tight');plt.close(fig)
    # Native pixels from window-only screen recordings, cropped to the application.
    # Source masters are 3456×1812; figure labels remain editable vector text.
    def excerpt(name, source, box, width=6.7):
        im=plt.imread(FIG/source);x0,y0,x1,y1=box
        fig=plt.figure(figsize=(width,width*(y1-y0)/(x1-x0)))
        ax=fig.add_axes([0,0,1,1]);ax.imshow(im);ax.set_xlim(x0,x1);ax.set_ylim(y1,y0);ax.axis('off')
        fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight',pad_inches=0,dpi=600)
        fig.savefig(FIG/(name+'.png'),bbox_inches='tight',pad_inches=0,dpi=600);plt.close(fig)
    excerpt('atlas_overview','atlas_overview_capture.png',(428,8,3404,1468))
    excerpt('atlas_cohort','atlas_cohort_capture.png',(428,8,3404,1468))
    excerpt('atlas_grammar','atlas_grammar_capture.png',(428,138,3404,1702))
    excerpt('atlas_variants','atlas_variants_capture.png',(428,280,3404,1652))
    excerpt('atlas_alignment','atlas_alignment_capture.png',(428,74,3404,1760))
    # Equal-height panels preserve native proportions; only A/B are printed.
    from PIL import Image
    panels=[Image.open(FIG/'atlas_grammar_capture.png').crop((428,138,1588,1702)),
            Image.open(FIG/'atlas_pathways_capture.png').crop((428,412,2228,1562))]
    gap=.14; width=6.7
    aspects=[im.width/im.height for im in panels]
    height=(width-gap)/sum(aspects)
    fig=plt.figure(figsize=(width,height+.22));left=0
    for letter,im,aspect in zip(['A','B'],panels,aspects):
        panel_width=height*aspect
        ax=fig.add_axes([left/width,0,panel_width/width,height/(height+.22)])
        ax.imshow(im);ax.axis('off')
        fig.text(left/width,(height+.05)/(height+.22),letter,fontfamily='Times New Roman',fontsize=10)
        left+=panel_width+gap
    fig.savefig(FIG/'atlas_readings.pdf',dpi=600)
    fig.savefig(FIG/'atlas_readings.png',dpi=600);plt.close(fig)

if __name__=='__main__':main()
