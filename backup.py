"""Run only after stopping the archive server; destination may be a shared folder."""
from pathlib import Path
import os,zipfile,datetime
src=Path(os.environ.get('ARCHIVE_DATA',Path(__file__).parent/'data')).resolve()
if input('Stop the archive server first. Type STOPPED to continue: ')!='STOPPED':raise SystemExit('Cancelled')
dest=Path(input('Backup folder path: ').strip()).resolve();dest.mkdir(parents=True,exist_ok=True)
if dest==src or src in dest.parents:raise SystemExit('Choose a folder outside the data folder.')
if not (src/'archive.db').exists():raise SystemExit('Archive database not found.')
out=dest/('ERArchive-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for f in src.rglob('*'):
  if f.is_file():z.write(f,str(f.relative_to(src)))
print('Backup saved:',out)
