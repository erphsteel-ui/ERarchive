from app import db
from werkzeug.security import generate_password_hash
from getpass import getpass
import re
name=input('Reader account name: ').strip()
if not re.fullmatch(r'[A-Za-z0-9_-]{2,40}',name): raise SystemExit('Use 2-40 letters, digits, underscores or hyphens.')
pw=getpass('Password (12+ characters): ')
if len(pw)<12 or pw!=getpass('Confirm password: '): raise SystemExit('Password invalid or does not match.')
with db() as c:
 if c.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone():raise SystemExit('Account already exists. Use app.py --user NAME --role viewer to reset.')
 c.execute('INSERT INTO users VALUES(?,?,?)',(name,generate_password_hash(pw),'viewer'))
print('Reader account created.')
