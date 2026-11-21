"""Editable draft templates and DOCX layout guided by GOST R 7.0.97-2025.

An organisation must provide its own approved blank and real requisites.
"""
from datetime import datetime
from io import BytesIO
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

KINDS = {
    'operator': 'Служебная записка исполнителю',
    'order': 'Проект распоряжения руководителя',
    'carrier': 'Сопроводительное письмо перевозчику',
    'driver': 'Краткая инструкция водителю',
}
CHANGE_ACTIONS = {'Временное изменение маршрута', 'Укороченные рейсы'}
APPROVED = {'Утверждено', 'Готово к доведению'}


def driver_allowed(item):
    d, p = item['decision'], item['payload']
    if d.get('action') in CHANGE_ACTIONS:
        return bool(d.get('route', '').strip() and d.get('stops', '').strip() and p.get('stops_known') and
                    (p.get('detour_confirmed') if d['action'] == 'Временное изменение маршрута' else p.get('turnaround_confirmed')))
    return True


def value(data, key, label):
    return str(data.get(key) or '').strip() or f'[{label}]'


def incident_time(raw):
    try:
        return datetime.fromisoformat(raw).strftime('%d.%m.%Y %H:%M')
    except (TypeError, ValueError):
        return '[время происшествия]'


def measure_text(action, routes, route, stops):
    if action == 'Временное изменение маршрута':
        return f'организовать временный объезд на маршрутах {routes}'
    if action == 'Укороченные рейсы':
        return f'организовать укороченные рейсы на маршрутах {routes}'
    if action == 'Использование резервного транспорта':
        return f'предусмотреть выпуск резервного транспорта на маршруты {routes} после подтверждения готовности'
    if action == 'Временная корректировка выпуска':
        return f'скорректировать выпуск на маршрутах {routes} согласно подтверждённому плану'
    if action == 'Ожидание восстановления движения':
        return f'сохранить действующую схему движения маршрутов {routes} и контролировать восстановление проезда'
    return '[меру выбирает специалист]'


def driver_action(action):
    if action == 'Временное изменение маршрута': return 'После доведения утверждённой схемы следовать по указанной трассе объезда'
    if action == 'Укороченные рейсы': return 'После доведения решения завершать рейс у указанного разворотного пункта'
    if action == 'Использование резервного транспорта': return 'После выпуска резервной машины выполнять рейс по заданию диспетчера'
    if action == 'Временная корректировка выпуска': return 'Работать по временному графику, доведённому диспетчером'
    if action == 'Ожидание восстановления движения': return 'Следовать по действующей схеме, соблюдать указания диспетчера'
    return '[действие уточняется специалистом]'


def render(item, kind):
    if kind not in KINDS:
        raise ValueError('Неизвестный вид документа')
    if kind == 'driver' and not driver_allowed(item):
        raise ValueError('Инструкция водителю недоступна: трасса, остановки или схема не подтверждены')
    p, d = item['payload'], item['decision']
    org = value(d, 'organization', 'наименование организации')
    carrier = value(d, 'carrier', 'наименование перевозчика')
    signer = value(d, 'signer_name', 'Ф.И.О. подписанта')
    signer_title = value(d, 'signer_title', 'должность подписанта')
    date, number = value(d, 'document_date', 'дата подписания'), value(d, 'document_number', 'регистрационный номер')
    responsible = value(d, 'responsible', 'ответственный исполнитель')
    place, routes = value(p, 'place', 'место происшествия'), value(p, 'routes', 'номера маршрутов')
    period = value(d, 'period', 'начало и окончание действия меры')
    route, stops = value(d, 'route', 'утверждённая трасса'), value(d, 'stops', 'перечень остановок')
    action = d.get('action') or ''
    measure = measure_text(action, routes, route, stops)
    description = value(p, 'description', 'описание происшествия')
    incident_number = item['id']
    draft = 'ПРОЕКТ — НЕ ПОДПИСАНО' if kind != 'driver' or item['status'] not in APPROVED else 'ДЛЯ ДОВЕДЕНИЯ ПОСЛЕ УТВЕРЖДЕНИЯ'
    date_number = f'от {date} № {number}'
    note = (d.get('notes') or '').strip()
    if kind == 'operator':
        lines = [org, f'Кому: {responsible}', draft, 'СЛУЖЕБНАЯ ЗАПИСКА', date_number,
                 'О проверке мер при нарушении движения', '',
                 f'В {incident_time(p.get("time"))} поступило сообщение о происшествии № {incident_number}: {description}',
                 f'Место: {place}. Затронутые маршруты: {routes}. Предполагаемая продолжительность: {value(p, "duration_minutes", "минуты")} мин.',
                 f'Предварительно предлагается {measure}.',
                 'Прошу проверить исходные сведения, безопасность исполнения и возможность применения меры; уточнить трассу, остановки и сроки. Решение передать на согласование.',
                 f'Ответственный за подготовку: {responsible}.']
        if action in CHANGE_ACTIONS: lines.append(f'Для проверки: трасса {route}; остановки {stops}.')
        if note: lines.append(f'Уточнение специалиста: {note}')
        return '\n'.join(lines + ['', 'Подпись: [должность оператора] __________ [Ф.И.О. оператора]'])
    if kind == 'order':
        lines = [org, draft, 'РАСПОРЯЖЕНИЕ', date_number,
                 'О временных мерах при нарушении движения', '',
                 f'В связи с происшествием № {incident_number} (место: {place}) и нарушением движения маршрутов {routes} РАСПОРЯЖАЮСЬ:',
                 f'1. {measure[0].upper() + measure[1:]}.',
                 f'2. Установить период действия меры: {period}.',
                 f'3. {responsible} обеспечить проверку безопасности, доведение утверждённого решения до {carrier} и контроль исполнения.',
                 '4. При изменении обстановки сообщить диспетчеру и представить предложения по восстановлению обычной схемы движения.']
        if action in CHANGE_ACTIONS: lines.insert(8, f'Трасса: {route}. Остановки: {stops}.')
        if note: lines.append(f'Дополнительное указание: {note}')
        return '\n'.join(lines + ['', f'Подпись: {signer_title} __________ {signer}'])
    if kind == 'carrier':
        lines = [org, f'Справочные данные: {value(d, "organization_details", "адрес, телефон, e-mail, ОГРН и ИНН/КПП при необходимости")}',
                 f'Кому: {carrier}', draft, date_number,
                 'О временном порядке работы маршрутов', '',
                 f'Сообщаем о нарушении движения по происшествию № {incident_number}. Место: {place}. Затронуты маршруты {routes}.',
                 f'На рассмотрение направляется мера: {measure}. Предполагаемый период: {period}.',
                 'Просим проверить возможность исполнения, сообщить о препятствиях и назначить контактное лицо. Доведение указаний водителям допускается после утверждения решения и подтверждения условий движения.']
        if action in CHANGE_ACTIONS: lines.append(f'Для проверки: трасса {route}; остановки {stops}.')
        return '\n'.join(lines + [f'Ответственный за взаимодействие: {responsible}.', '', f'Подпись: {signer_title} __________ {signer}'])
    lines = [org, f'Кому: водителям маршрутов {routes}', draft, 'ОПЕРАТИВНАЯ ИНСТРУКЦИЯ',
             date_number, 'О порядке движения на период нарушения', '',
             f'Место: {place}. Период: {period}.',
             f'Действие: {driver_action(action)}.']
    if action in CHANGE_ACTIONS: lines += [f'Трасса: {route}.', f'Остановки: {stops}.']
    lines += [f'Связь с ответственным: {responsible}.',
              'При невозможности безопасного выполнения немедленно остановить изменение схемы и сообщить диспетчеру. Исполнять только после официального доведения утверждённого решения.',
              '', 'Подпись: [должность лица, доводящего инструкцию] __________ [Ф.И.О.]']
    return '\n'.join(lines)


def docx_bytes(body, kind):
    if kind not in KINDS: raise ValueError('Неизвестный вид документа')
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    section.top_margin = section.bottom_margin = Cm(2)
    section.header_distance = Cm(1)
    section.different_first_page_header_footer = True
    normal = document.styles['Normal']
    normal.font.name, normal.font.size = 'Times New Roman', Pt(12)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.first_line_indent = Cm(1.25)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    header._p.append(field)
    for index, raw in enumerate(body.splitlines()):
        line = raw.strip()
        paragraph = document.add_paragraph()
        if not line:
            paragraph.paragraph_format.space_after = Pt(4)
        elif index == 0:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line).bold = True
        elif line.startswith('Кому: '):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line[6:])
        elif line.startswith('Справочные данные: '):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line.split(': ', 1)[1]).font.size = Pt(10)
        elif line.startswith(('ПРОЕКТ', 'ДЛЯ ДОВЕДЕНИЯ')):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line).italic = True
        elif line in {'СЛУЖЕБНАЯ ЗАПИСКА', 'РАСПОРЯЖЕНИЕ', 'ОПЕРАТИВНАЯ ИНСТРУКЦИЯ'}:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line).bold = True
        elif line.startswith(('от ', 'Об ', 'О ')) and len(line) < 120:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line).bold = line.startswith(('Об ', 'О '))
        elif line.startswith('Подпись: '):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.first_line_indent = Cm(0)
            signature = re.match(r'^Подпись: (.+?)\s+_{4,}\s+(.+)$', line)
            if signature:
                table = document.add_table(rows=1, cols=3)
                table.autofit = False
                for cell, content, width in zip(table.rows[0].cells,
                                                (signature.group(1), '__________', signature.group(2)),
                                                (Cm(7), Cm(3), Cm(6.5))):
                    cell.width = width
                    cell.text = content
                    cell.paragraphs[0].paragraph_format.first_line_indent = Cm(0)
                paragraph._p.addnext(table._tbl)
            else:
                paragraph.add_run(line[9:])
        elif re.match(r'^\d+\.', line):
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.add_run(line)
        else:
            paragraph.add_run(line)
    document.core_properties.title = KINDS[kind]
    result = BytesIO()
    document.save(result)
    return result.getvalue()
