/* Nora public-form quality checks: local, deterministic, and network-free. */
(function(root){
  'use strict';

  const FA='۰۱۲۳۴۵۶۷۸۹',AR='٠١٢٣٤٥٦٧٨٩';
  const EXCLUSIONS=[
    'دانشگاه','دانشکده','مدرسه','مؤسسه','موسسه','شرکت','سازمان','محصول','رویداد','عنوان','موضوع',
    'کاربری','رشته','درس','پروژه','برند','گروه','طرح','کانال','فروشگاه','university','college','school',
    'company','organization','institution','product','event','title','subject','course','project','brand',
    'username','user name'
  ];
  const PLACEHOLDERS=new Set([
    'test','testing','unknown','anonymous','anon','none','asdf','qwerty','xxx',
    'نام','ناشناس','بدوننام','تست'
  ]);
  const PLACEHOLDER_VALUES=new Set([
    'test','testing','testanswer','sample','sampletext','example','placeholder','dummy','unknown',
    'anonymous','anon','none','null','undefined','na','asdf','asdfgh','qwerty','qwertyuiop','foobar',
    'loremipsum','xxx','johndoe','janedoe','yourname','namehere','firstname','lastname',
    'نام','نامنمونه','ناشناس','بدوننام','تست','نمونه','مثال','پاسخنمونه','متننمونه','نامخودراواردکنید'
  ]);
  const TEXT_FIELD_TYPES=new Set(['text','area','fullname','uni','job','edu','address','location','province','coupon']);
  const PATTERN_FIELD_TYPES=new Set([...TEXT_FIELD_TYPES,'number','amount','price','mobile','nid','email',
    'date','datetime','time','slot','rating','scale','bars']);
  const KEYBOARD_ROWS=['qwertyuiop','asdfghjkl','zxcvbnm','1234567890','ضصثقفغعهخحجچ','شسیبلاتنمکگ','ظطزرذدپو'];
  const KEYBOARD_RUNS=new Set();
  KEYBOARD_ROWS.forEach(row=>{
    const chars=[...row];
    for(let i=0;i<=chars.length-4;i++){
      const run=chars.slice(i,i+4).join('');KEYBOARD_RUNS.add(run);KEYBOARD_RUNS.add([...run].reverse().join(''));
    }
  });

  function normalizeDigits(value){
    return String(value==null?'':value).replace(/[۰-۹٠-٩]/g,d=>{
      const fa=FA.indexOf(d);return String(fa>=0?fa:AR.indexOf(d));
    });
  }
  function cleanText(value){
    return String(value==null?'':value).normalize('NFKC').toLowerCase()
      .replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/ـ/g,'')
      .replace(/\p{M}/gu,'').replace(/[\u200c\u200e\u200f]/g,' ')
      .replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();
  }
  function fieldType(field){return String(field&&(field.t||field.type)||'').trim().toLowerCase()}
  function fieldLabel(field){return String(field&&(field.l||field.label)||'')}
  function fieldKey(field){return String(field&&(field.id||field.k||field.key)||'')}
  function qualityTokens(normalized){return normalized.match(/[\p{L}\p{N}]+/gu)||[]}
  function compactAlphanumeric(normalized){return [...normalized].filter(char=>/[\p{L}\p{N}]/u.test(char)).join('')}
  function hasRepeatedSequence(tokens){
    for(const token of tokens){
      const chars=[...token];
      if(chars.length>=4&&new Set(chars).size===1)return true;
      for(let i=0;i<=chars.length-5;i++)if([...chars.slice(i,i+5)].every(char=>char===chars[i]))return true;
      for(const unitSize of [2,3]){
        if(chars.length>=unitSize*3&&chars.length%unitSize===0
            &&token===chars.slice(0,unitSize).join('').repeat(chars.length/unitSize))return true;
      }
    }
    return false;
  }
  function hasKeyboardSequence(tokens){
    return tokens.some(token=>{
      const chars=[...token];
      for(let i=0;i<=chars.length-4;i++)if(KEYBOARD_RUNS.has(chars.slice(i,i+4).join('')))return true;
      return false;
    });
  }
  function hasRepeatedWord(tokens){
    if(tokens.length<2)return false;
    if(new Set(tokens).size===1)return true;
    const counts=new Map();tokens.forEach(token=>counts.set(token,(counts.get(token)||0)+1));
    return [...counts.values()].some(count=>count>=3);
  }
  function isPlaceholderEmail(value){
    const [local='',domain='']=String(value||'').toLowerCase().split('@');
    if(!domain)return false;
    const labels=domain.split('.'),lastTwo=labels.slice(-2).join('.');
    return PLACEHOLDER_VALUES.has(compactAlphanumeric(cleanText(local)))
      ||['example.com','example.org','example.net','test.com'].includes(lastTwo)||domain==='invalid';
  }
  function isPersonNameField(field){
    const kind=fieldType(field),descriptor=cleanText(fieldLabel(field)+' '+fieldKey(field));
    if(kind==='fullname')return true;
    if(EXCLUSIONS.some(term=>descriptor.includes(term)))return false;
    if(!['text','area'].includes(kind))return false;
    return /(?:نام|اسم)/u.test(descriptor)||/\b(?:name|full name|first name|last name|participant|applicant)\b/.test(descriptor);
  }
  function isBirthDateField(field){
    const kind=fieldType(field);
    if(!['date','datetime'].includes(kind))return false;
    const descriptor=cleanText(fieldLabel(field)+' '+fieldKey(field));
    return /(?:تولد|زادروز|متولد)/u.test(descriptor)
      ||/\b(?:dob|birthday|birthdate|birth date|date of birth|date born)\b/.test(descriptor);
  }
  let jalaliFormatter=null;
  try{
    jalaliFormatter=new Intl.DateTimeFormat('en-US-u-ca-persian-nu-latn',{
      timeZone:'Asia/Tehran',year:'numeric',month:'numeric',day:'numeric'
    });
  }catch(error){}
  function gregorianToJalali(gy,gm,gd){
    const monthDays=[0,31,59,90,120,151,181,212,243,273,304,334];
    const gy2=gy-1600,gm2=gm-1,gd2=gd-1;
    let gDayNo=365*gy2+Math.floor((gy2+3)/4)-Math.floor((gy2+99)/100)
      +Math.floor((gy2+399)/400)+monthDays[gm2]+gd2;
    const gregorianLeap=gy%4===0&&(gy%100!==0||gy%400===0);
    if(gm>2&&gregorianLeap)gDayNo++;
    let jDayNo=gDayNo-79,jNp=Math.floor(jDayNo/12053);
    jDayNo%=12053;
    let jy=979+33*jNp+4*Math.floor(jDayNo/1461);
    jDayNo%=1461;
    if(jDayNo>=366){jy+=Math.floor((jDayNo-1)/365);jDayNo=(jDayNo-1)%365}
    if(jDayNo<186)return [jy,1+Math.floor(jDayNo/31),1+jDayNo%31];
    jDayNo-=186;return [jy,7+Math.floor(jDayNo/30),1+jDayNo%30];
  }
  function jalaliToday(now){
    const instant=now instanceof Date?now:new Date();
    try{
      const parts=jalaliFormatter&&jalaliFormatter.formatToParts(instant);
      const get=name=>Number(parts&&parts.find(part=>part.type===name)?.value);
      const date=[get('year'),get('month'),get('day')];
      if(date.every(Number.isFinite))return date;
    }catch(error){}
    let local=instant;
    try{local=new Date(instant.toLocaleString('en-US',{timeZone:'Asia/Tehran'}))}catch(error){}
    return gregorianToJalali(local.getFullYear(),local.getMonth()+1,local.getDate());
  }
  function jalaliMonthDays(year,month){
    const shared=root.NORA_UI&&root.NORA_UI.jalaliDaysInMonth;
    if(typeof shared==='function')return shared(Number(year),Number(month));
    if(month>=1&&month<=6)return 31;
    if(month>=7&&month<=11)return 30;
    if(month===12)return 29;
    return 0;
  }
  function parseDate(value){
    let text=normalizeDigits(value).trim().split(/\s*(?:ساعت|—)\s*/u)[0].trim();
    const match=text.match(/^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$/);
    if(!match)return null;
    let year=Number(match[1]),month=Number(match[2]),day=Number(match[3]);
    if(year>=1900){
      const date=new Date(Date.UTC(year,month-1,day));
      if(date.getUTCFullYear()!==year||date.getUTCMonth()+1!==month||date.getUTCDate()!==day)return null;
      return gregorianToJalali(year,month,day);
    }
    const max=jalaliMonthDays(year,month);
    return month>=1&&month<=12&&day>=1&&day<=max?[year,month,day]:null;
  }
  function tuple(value){
    if(Array.isArray(value)&&value.length===3){const parts=value.map(Number);return parts.every(Number.isFinite)?parts:null}
    if(value&&typeof value==='object'){
      const parts=[Number(value.year),Number(value.month),Number(value.day)];
      return parts.every(Number.isFinite)?parts:null;
    }
    return null;
  }
  function compare(left,right){
    for(let index=0;index<3;index++){if(left[index]!==right[index])return left[index]<right[index]?-1:1}
    return 0;
  }
  function analyze(field,value,options){
    const opts=options&&typeof options==='object'?options:{};
    if(value==null||Array.isArray(value)||typeof value==='object')return [];
    const text=String(value);if(!text.trim())return [];
    const findings=[],kind=fieldType(field),normalized=cleanText(normalizeDigits(text)),tokens=qualityTokens(normalized),
      compact=compactAlphanumeric(normalized),personName=isPersonNameField(field);
    if(personName){
      const letters=[...normalized].filter(char=>/\p{L}/u.test(char));
      const repeatedLetterToken=(letters.length>=3&&new Set(letters).size===1)||tokens.some(token=>{
        const tokenLetters=[...token].filter(char=>/\p{L}/u.test(char));
        return tokenLetters.length>=3&&new Set(tokenLetters).size===1;
      });
      if(!letters.length){
        findings.push({code:'name_has_no_letters',severity:'error',message:'برای این فیلد نام را با حروف بنویسید؛ عدد یا نماد به‌تنهایی نام نیست.'});
      }else if(letters.length<2){
        findings.push({code:'name_too_short',severity:'error',message:'نام باید دست‌کم دو حرف داشته باشد؛ آن را بازبینی کنید.'});
      }else if(repeatedLetterToken){
        findings.push({code:'suspicious_repeated_name',severity:'error',message:'نام یا یکی از واژه‌های آن از تکرار یک حرف ساخته شده است؛ نام را اصلاح کنید.'});
      }else if(PLACEHOLDERS.has(compact)){
        findings.push({code:'placeholder_name',severity:'error',message:'این پاسخ شبیه نام نمونه یا جای‌نگهدار است؛ نام فرد را وارد کنید.'});
      }else if(PLACEHOLDER_VALUES.has(compact)){
        findings.push({code:'placeholder_name',severity:'warning',message:'این نام شبیه مقدار نمونه است؛ آن را بازبینی کنید و اگر درست است ادامه دهید.'});
      }else if(hasRepeatedSequence(tokens)){
        findings.push({code:'repetitive_name_pattern',severity:'warning',message:'نام الگوی تکراری دارد؛ آن را بازبینی کنید و اگر درست است ادامه دهید.'});
      }else if(hasKeyboardSequence(tokens)){
        findings.push({code:'keyboard_mash',severity:'warning',message:'نام شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ آن را بازبینی کنید و اگر درست است ادامه دهید.'});
      }else if(hasRepeatedWord(tokens)){
        findings.push({code:'repeated_name_token',severity:'warning',message:'یک واژه در نام چندبار تکرار شده است؛ اگر عمدی است می‌توانید ادامه دهید.'});
      }
    }
    if(TEXT_FIELD_TYPES.has(kind)&&!personName){
      if(PLACEHOLDER_VALUES.has(compact)){
        findings.push({code:'placeholder_answer',severity:'warning',message:'این پاسخ شبیه متن نمونه یا جای‌نگهدار است؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.'});
      }else if(hasRepeatedSequence(tokens)){
        findings.push({code:'repetitive_answer_pattern',severity:'warning',message:'این پاسخ الگوی تکراری دارد؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.'});
      }else if(hasKeyboardSequence(tokens)){
        findings.push({code:'keyboard_mash',severity:'warning',message:'این پاسخ شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ مقدار را بازبینی کنید.'});
      }else if(hasRepeatedWord(tokens)){
        findings.push({code:'repeated_answer_token',severity:'warning',message:'یک واژه در این پاسخ چندبار تکرار شده است؛ آن را بازبینی کنید و اگر عمدی است ادامه دهید.'});
      }else if(![...normalized].some(char=>/[\p{L}\p{N}]/u.test(char))){
        findings.push({code:'answer_only_symbols',severity:'warning',message:'این پاسخ فقط از نشانه‌ها تشکیل شده است؛ اگر پاسخ کامل است می‌توانید ادامه دهید.'});
      }else if(['text','area','address','location'].includes(kind)&&compact.length<=1){
        findings.push({code:'very_short_answer',severity:'warning',message:'این پاسخ بسیار کوتاه است؛ اگر کامل است می‌توانید ادامه دهید.'});
      }
    }
    if(PATTERN_FIELD_TYPES.has(kind)&&!TEXT_FIELD_TYPES.has(kind)&&!personName){
      if(hasRepeatedSequence(tokens)){
        findings.push({code:'repetitive_input_pattern',severity:'warning',message:'این مقدار الگوی تکراری دارد؛ آن را بازبینی کنید و اگر درست است ادامه دهید.'});
      }else if(hasKeyboardSequence(tokens)){
        findings.push({code:'keyboard_sequence',severity:'warning',message:'این مقدار شبیه دنبالهٔ کلیدهای صفحه‌کلید است؛ آن را بازبینی کنید.'});
      }
    }
    if(kind==='email'&&isPlaceholderEmail(text)){
      findings.push({code:'placeholder_email',severity:'warning',message:'نشانی ایمیل شبیه نمونه یا دامنهٔ آزمایشی است؛ آن را بازبینی کنید.'});
    }
    if(isBirthDateField(field)){
      const parts=parseDate(text),today=tuple(opts.today)||jalaliToday(opts.now);
      if(parts){
        const relation=compare(parts,today);
        if(relation>0){
          findings.push({code:'birth_date_in_future',severity:'error',message:'تاریخ تولد نمی‌تواند در آینده باشد؛ تاریخ را بازبینی کنید.'});
        }else if(relation===0){
          findings.push({code:'birth_date_is_today',severity:'warning',requiresConfirmation:true,
            message:'تاریخ تولد واردشده برابر با امروز است؛ برای نوزاد تازه‌متولدشده می‌تواند درست باشد. در غیر این صورت تاریخ را اصلاح کنید.'});
        }else if(today[0]-parts[0]>110){
          findings.push({code:'birth_date_unusually_old',severity:'warning',
            message:'این تاریخ تولد بیش از ۱۱۰ سال قبل است؛ اگر درست است می‌توانید ادامه دهید، وگرنه تاریخ را بازبینی کنید.'});
        }
      }
    }
    return findings;
  }

  root.NORA_FORM_QUALITY=Object.freeze({
    version:'nora-quality-2',
    analyze,
    cleanText,
    currentJalaliDate:jalaliToday,
    isBirthDateField,
    isPersonNameField,
    normalizeDigits,
    parseJalaliDate:parseDate,
  });
})(typeof window==='undefined'?globalThis:window);
