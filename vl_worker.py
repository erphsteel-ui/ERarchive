"""One local CPU VL job; JSON only, no visualization/font or network access."""
import os,sys,json,time,socket
from pathlib import Path
os.environ.update(PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONUTF8='1')
def offline(*args,**kwargs):
    raise OSError('정밀 인식은 로컬 모델만 사용합니다. 필요한 모델 파일을 먼저 설치하세요.')
socket.create_connection=offline
socket.socket.connect=offline
socket.socket.connect_ex=offline

def main():
    image,out,layout,vl=sys.argv[1:]
    from paddleocr import PaddleOCRVL
    started=time.monotonic()
    pipeline=PaddleOCRVL(pipeline_version='v1.6',device='cpu',enable_mkldnn=False,cpu_threads=4,use_queues=False,
        layout_detection_model_name='PP-DocLayoutV3',layout_detection_model_dir=layout,
        vl_rec_model_name='PaddleOCR-VL-1.6-0.9B',vl_rec_model_dir=vl,
        use_doc_orientation_classify=False,use_doc_unwarping=False,
        use_chart_recognition=False,use_seal_recognition=False,use_ocr_for_image_block=False)
    loaded=time.monotonic()-started;started=time.monotonic()
    for result in pipeline.predict(image):result.save_to_json(out)
    print('ER_VL '+json.dumps({'load_seconds':round(loaded,1),'predict_seconds':round(time.monotonic()-started,1)}),flush=True)
if __name__=='__main__':main()
