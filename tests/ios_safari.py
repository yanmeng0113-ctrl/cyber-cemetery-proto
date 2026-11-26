"""Play two public game URLs using the Mobile Safari W3C WebDriver session."""
import json
import os
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path


evidence = Path('safari-evidence')
evidence.mkdir(exist_ok=True)
driver = 'http://127.0.0.1:4444'
session = ''


def call(method, route, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(driver + session + route, data=body, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)['value']
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()[:1800]) from exc


def wait(check, seconds=45):
    end = time.monotonic() + seconds
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() >= end:
            raise TimeoutError(check)
        time.sleep(0.5)


def js(script, *args):
    return call('POST', '/execute/sync', {'script': script, 'args': args})


def visible(selector):
    return js('const e=document.querySelector(arguments[0]); return !!(e && e.getClientRects().length && getComputedStyle(e).visibility!=="hidden");', selector)


def element(selector):
    wait(lambda: visible(selector))
    return next(iter(call('POST','/element',{'using':'css selector','value':selector}).values()))


def click(selector):
    # SafariDriver's element-click can turn into long-press on a busy simulator.
    # Native touches and typing are tested independently with XCTest.
    element(selector)
    wait(lambda: not js('return !!document.querySelector(arguments[0]).disabled',selector))
    js('const e=document.querySelector(arguments[0]); if(e.disabled) throw Error("disabled: "+arguments[0]); e.click()', selector)


def confirm_recipient():
    click('.prayer-form button[type=submit]')
    wait(lambda:'River' in text_of('.prayer-current'))


def type_into(selector, text):
    element(selector)
    js('const e=document.querySelector(arguments[0]); e.focus(); e.value=arguments[1]; e.dispatchEvent(new Event("input",{bubbles:true})); e.dispatchEvent(new Event("change",{bubbles:true}));', selector, text)
    assert js('return document.querySelector(arguments[0]).value',selector)==text


def screenshot(name):
    subprocess.run(['xcrun','simctl','io',os.environ['SIM_UDID'],'screenshot',str(evidence/(name+'.png'))],check=True)


def text_of(selector):
    return js('return document.querySelector(arguments[0])?.innerText||""', selector)


def garden():
    call('POST','/url',{'url':'https://cyber-cemetery-proto.pages.dev/'})
    assert 'v0.64.1' in call('GET','/title')
    click('#btnTitleMain')
    click('[data-av=a4]')
    click('#btnMapTop')
    click('#btnNearestPlot')
    wait(lambda:visible('#btnRegHere'),60)
    click('#btnRegHere')
    type_into('#regName','Momo')
    screenshot('garden-name-keyboard')
    click('#btnRegister')
    click('#btnSkipCer')
    click('#btnFirstCandle')
    wait(lambda:'Momo' in text_of('#infoName'))
    click('#btnMapTop')
    click('.mapBadge.home')
    click('[data-act=feed]')
    click('[data-act=play]')
    def care_recorded():
        counts=js("return document.querySelector('#houseStats').textContent").split()
        compact=''.join(counts)
        return '被投喂1' in compact and '被陪玩1' in compact
    wait(care_recorded)
    screenshot('garden-house')
    click('#btnLeave')
    click('#btnDrawer')
    click('#btnLoginGift')
    click('#btnCheckin')
    call('POST','/refresh',{})
    click('#btnTitleLoad')
    click('#btnDrawer')
    wait(lambda:'今日已签到' in text_of('#checkinLabel') and '今日物资已领' in text_of('#giftLabel'))


def mountain():
    call('POST','/url',{'url':'https://yunqi-shanzhong-v2-play.pages.dev/'})
    type_into('#nick','River')
    screenshot('mountain-name-keyboard')
    click('#enter')
    wait(lambda: visible('#lookPicker') or visible('#tripSkip') or visible('#btnMap'))
    if visible('#lookPicker'):
        click('#lookChoices button')
        click('#lookConfirm')
    wait(lambda:visible('#tripSkip') or visible('#btnMap'))
    if visible('#tripSkip'):
        click('#tripSkip')
    click('#btnMap')
    click('.mpAct[data-hot="hall"]')
    wait(lambda:visible('.prayer-panel'),100)
    type_into('.prayer-form input','River')
    confirm_recipient()
    screenshot('mountain-hall')
    click('#mgExit')
    click('#btnMap')
    click('.mpAct[data-hot="qin"]')
    wait(lambda:visible('.prayer-panel'),100)
    type_into('.prayer-form input','River')
    confirm_recipient()
    js('const b=[...document.querySelectorAll("button")].find(e=>e.innerText.trim()==="点一盏烛"&&e.getClientRects().length); if(!b||b.disabled)throw Error("candle unavailable"); b.click()')
    click('.prayer-paper[data-kind="cloud"]')
    click('.prayer-sheet-control')
    wait(lambda:'送纸 1 张' in text_of('.prayer-current'))
    screenshot('mountain-offering')


def main():
    global session
    caps={'browserName':'Safari','platformName':'iOS','safari:useSimulator':True,
          'safari:deviceUDID':os.environ['SIM_UDID']}
    for i in range(8):
        try:
            created=call('POST','/session',{'capabilities':{'alwaysMatch':caps}})
            break
        except (OSError,RuntimeError) as error:
            if i==7:
                raise
            print('Driver startup:',error,flush=True)
            time.sleep(3)
    session='/session/'+created['sessionId']
    capabilities=created['capabilities']
    assert capabilities['platformName'].lower()=='ios' and capabilities['safari:useSimulator']
    print('SIMULATOR',capabilities['safari:deviceName'],capabilities['safari:platformVersion'],capabilities['browserVersion'],flush=True)
    report={'capabilities':capabilities, 'games':{}}
    for fn in (garden,mountain):
        try:
            fn()
            report['games'][fn.__name__]='PASS'
        except Exception:
            traceback.print_exc()
            report['games'][fn.__name__]='FAIL'
            try:
                print('Visible game state:',js("return document.body.innerText.slice(0,750)"),flush=True)
            except Exception:
                pass
            screenshot(fn.__name__+'-failure')
        print(fn.__name__,report['games'][fn.__name__],flush=True)
    (evidence/'results.json').write_text(json.dumps(report,indent=2))
    call('DELETE','')
    if 'FAIL' in report['games'].values():
        raise SystemExit(1)


if __name__=='__main__':
    main()
