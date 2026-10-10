# Contact sheet of chosen frames of a rendered video (review aid): python scripts/edwall-video-sheet.py <mp4> <out.jpg> f1,f2,...
import cv2, sys, numpy as np
v=cv2.VideoCapture(sys.argv[1]); n=int(v.get(cv2.CAP_PROP_FRAME_COUNT)); fr=[int(x) for x in sys.argv[3].split(',')]
tiles=[]
for f in fr:
    v.set(cv2.CAP_PROP_POS_FRAMES,f); ok,im=v.read()
    im=cv2.resize(im,(960,540)); cv2.putText(im,str(f),(10,30),0,1,(0,0,255),2); tiles.append(im)
while len(tiles)%2: tiles.append(np.zeros_like(tiles[0]))
cv2.imwrite(sys.argv[2], np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,len(tiles),2)]))
print(n)
