"""Долговечный журнал отправителя и имитатора WCS; обмен JSON/HTTP описан в docs."""
import json,sqlite3,hashlib,math

MAX_CODES=24
MAX_PAYLOAD_BYTES=128
MAX_MESSAGE_BYTES=16384

def canonical(message):
    if len(message['codes'])>MAX_CODES: raise ValueError('Превышен лимит значений')
    for d in message['codes']:
        if len(bytes.fromhex(d['payload_hex']))>MAX_PAYLOAD_BYTES:raise ValueError('Значение слишком длинное')
    body=json.dumps(message,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    if len(body.encode())>MAX_MESSAGE_BYTES:raise ValueError('Пакет слишком большой')
    return body

class Outbox:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, body TEXT NOT NULL, deadline REAL NOT NULL, ack INTEGER DEFAULT 0)')
    def put(self,message):
        body=canonical(message);mid=message['message_id'];deadline=message['deadline_s']
        if not math.isfinite(deadline):raise ValueError('Некорректный срок')
        old=self.db.execute('SELECT body FROM outbox WHERE id=?',(mid,)).fetchone()
        if old and old[0]!=body:raise ValueError('Конфликт message_id')
        with self.db:self.db.execute('INSERT OR IGNORE INTO outbox(id,body,deadline) VALUES (?,?,?)',(mid,body,deadline))
    def pending(self,now):
        return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM outbox WHERE ack=0 AND deadline>=? ORDER BY deadline',(now,))]
    def acknowledge(self,ack):
        if ack.get('receipt') not in ('accepted','duplicate'):return False
        with self.db:self.db.execute('UPDATE outbox SET ack=1 WHERE id=?',(ack['message_id'],))
        return True

class DurableWCS:
    """ACK подтверждает запись сообщения. Команда физической сортировки имеет отдельный статус."""
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, body TEXT NOT NULL, action TEXT NOT NULL, executed INTEGER DEFAULT 0)')
    def receive(self,message,now):
        if not math.isfinite(now):raise ValueError('Некорректное время')
        body=canonical(message);mid=message['message_id']
        old=self.db.execute('SELECT body,action FROM receipts WHERE id=?',(mid,)).fetchone()
        if old:
            if old[0]!=body:raise ValueError('Конфликт message_id')
            return {'message_id':mid,'receipt':'duplicate','sorting':'pending_or_recorded'}
        action='resolve_all_values' if now<=message['deadline_s'] and message['status']=='read' else 'exception_only'
        with self.db:self.db.execute('INSERT INTO receipts(id,body,action) VALUES (?,?,?)',(mid,body,action))
        return {'message_id':mid,'receipt':'accepted','sorting':'pending','action':action}
    def execute(self,message_id,now):
        row=self.db.execute('SELECT body,action,executed FROM receipts WHERE id=?',(message_id,)).fetchone()
        if not row:raise KeyError(message_id)
        msg=json.loads(row[0])
        if row[2]:return 'already_recorded'
        action=row[1] if now<=msg['deadline_s'] else 'exception_only'
        with self.db:self.db.execute('UPDATE receipts SET executed=1,action=? WHERE id=?',(action,message_id))
        return action
