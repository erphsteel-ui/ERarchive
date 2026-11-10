"""Persistent local OCR service. stdout is reserved for prefixed JSON replies."""
import os,sys,json,time,contextlib
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
os.environ['PYTHONUTF8']='1'
def main():
    det,rec=sys.argv[1:]; engine=None
    for line in sys.stdin:
        try:
            req=json.loads(line);started=time.monotonic();loaded=0
            with contextlib.redirect_stdout(sys.stderr):
                if engine is None:
                    from paddleocr import PaddleOCR
                    engine=PaddleOCR(device='cpu',enable_mkldnn=False,
                        text_detection_model_name='PP-OCRv5_server_det',text_detection_model_dir=det,
                        text_recognition_model_name='korean_PP-OCRv5_mobile_rec',text_recognition_model_dir=rec,
                        use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False)
                    loaded=time.monotonic()-started
                begin=time.monotonic()
                for result in engine.predict(req['image']):result.save_to_json(req['output'])
            reply={'ok':True,'load_seconds':round(loaded,2),'predict_seconds':round(time.monotonic()-begin,2)}
        except Exception as exc:reply={'ok':False,'error':str(exc)[-350:]}
        print('ER_RESULT '+json.dumps(reply),flush=True)
if __name__=='__main__':main()
