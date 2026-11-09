from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path('/Users/biancasawant/APART_6TH')
RESEARCH = ROOT / 'research'
FIGURES = RESEARCH / 'figures'
FIGURES.mkdir(parents=True, exist_ok=True)
DOCX = RESEARCH / 'CASCADE_Apart_Research_Submission.docx'

FONT_REG = '/System/Library/Fonts/Supplemental/Georgia.ttf'
FONT_BOLD = '/System/Library/Fonts/Supplemental/Georgia Bold.ttf'


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def make_coverage_figure(path: Path):
    im = Image.new('RGB', (1600, 700), 'white')
    d = ImageDraw.Draw(im)
    navy = '#294760'
    gray = '#9aa4ad'
    dark = '#1f252b'
    light = '#d9dde1'
    d.text((800, 35), 'Evidence coverage by message condition', font=font(40, True), fill=dark, anchor='ma')
    d.text((800, 88), 'Required facts represented (%)', font=font(24), fill='#535b62', anchor='ma')
    left, top, right, bottom = 155, 150, 1510, 575
    for value in range(0, 101, 25):
        y = bottom - (bottom-top)*value/100
        d.line((left, y, right, y), fill=light, width=2)
        d.text((left-25, y), str(value), font=font(21), fill=dark, anchor='rm')
    d.line((left, top, left, bottom), fill=dark, width=3)
    d.line((left, bottom, right, bottom), fill=dark, width=3)
    labels = ['Clear', 'Ambiguous', 'Omission']
    cited = [100, 33, 100]
    communicated = [100, 0, 100]
    centers = [390, 830, 1270]
    bw = 105
    for x, label, a, b in zip(centers, labels, cited, communicated):
        for xpos, val, color in [(x-bw-8, a, navy), (x+8, b, gray)]:
            y = bottom - (bottom-top)*val/100
            d.rectangle((xpos, y, xpos+bw, bottom), fill=color)
            d.text((xpos+bw/2, max(y-12, top-5)), f'{val}%', font=font(22, True), fill=dark, anchor='ms')
        d.text((x, bottom+38), label, font=font(24, True), fill=dark, anchor='ma')
    d.rectangle((500, 645, 528, 673), fill=navy)
    d.text((542, 659), 'Final cited evidence', font=font(21), fill=dark, anchor='lm')
    d.rectangle((890, 645, 918, 673), fill=gray)
    d.text((932, 659), 'Organic communicated evidence', font=font(21), fill=dark, anchor='lm')
    im.save(path, dpi=(300, 300))


def make_trajectory_figure(path: Path):
    im = Image.new('RGB', (1600, 660), 'white')
    d = ImageDraw.Draw(im)
    dark = '#1f252b'
    grid = '#d9dde1'
    colors = {'Clear':'#294760', 'Ambiguous':'#a45f36', 'Omission':'#767f87'}
    d.text((800, 34), 'Agent 4 private belief across rounds', font=font(40, True), fill=dark, anchor='ma')
    d.text((800, 84), 'Only ambiguity changed the correct NO report to UNKNOWN', font=font(24), fill='#535b62', anchor='ma')
    left, top, right, bottom = 210, 145, 1490, 520
    ys = {'NO': bottom-70, 'UNKNOWN': top+70}
    xs = [340, 850, 1360]
    for label, y in ys.items():
        d.line((left, y, right, y), fill=grid, width=2)
        d.text((left-28, y), label, font=font(23, True), fill=dark, anchor='rm')
    d.line((left, top, left, bottom), fill=dark, width=3)
    d.line((left, bottom, right, bottom), fill=dark, width=3)
    for x, label in zip(xs, ['Round 0', 'Round 1', 'Round 2']):
        d.text((x, bottom+38), label, font=font(23), fill=dark, anchor='ma')
    series = {'Clear':['NO','NO','NO'], 'Ambiguous':['NO','NO','UNKNOWN'], 'Omission':['NO','NO','NO']}
    offsets = {'Clear':-15, 'Ambiguous':0, 'Omission':15}
    for name, vals in series.items():
        pts = [(x, ys[v]+offsets[name]) for x,v in zip(xs, vals)]
        d.line(pts, fill=colors[name], width=7)
        for x,y in pts:
            d.ellipse((x-12,y-12,x+12,y+12), fill=colors[name], outline='white', width=3)
    legend_x = 455
    for name in ['Clear','Ambiguous','Omission']:
        d.line((legend_x, 605, legend_x+55, 605), fill=colors[name], width=7)
        d.text((legend_x+68,605), name, font=font(21), fill=dark, anchor='lm')
        legend_x += 300
    im.save(path, dpi=(300, 300))


def set_font(run, size=None, bold=None, italic=None, name='Georgia', color='000000'):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:ascii'), name)
    run._element.get_or_add_rPr().rFonts.set(qn('w:hAnsi'), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    return run


def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:fill'), fill)


def set_cell_margins(cell, top=70, start=70, bottom=70, end=70):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None:
        tcMar = OxmlElement('w:tcMar')
        tcPr.append(tcMar)
    for m, v in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = tcMar.find(qn(f'w:{m}'))
        if node is None:
            node = OxmlElement(f'w:{m}')
            tcMar.append(node)
        node.set(qn('w:w'), str(v))
        node.set(qn('w:type'), 'dxa')


def set_table_borders(table, color='D9D9D9', size='5'):
    tblPr = table._tbl.tblPr
    borders = tblPr.first_child_found_in('w:tblBorders')
    if borders is None:
        borders = OxmlElement('w:tblBorders')
        tblPr.append(borders)
    for edge in ('top','left','bottom','right','insideH','insideV'):
        tag = borders.find(qn(f'w:{edge}'))
        if tag is None:
            tag = OxmlElement(f'w:{edge}')
            borders.append(tag)
        tag.set(qn('w:val'),'single'); tag.set(qn('w:sz'),size); tag.set(qn('w:color'),color)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    run._r.append(fld)


def para(doc, text='', style=None, size=9.4, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=0, after=4, keep=False):
    p = doc.add_paragraph(style=style)
    p.alignment = align
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.03
    p.paragraph_format.keep_with_next = keep
    if text:
        set_font(p.add_run(text), size, bold, italic)
    return p


def heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7 if level == 1 else 4)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), 14 if level == 1 else 10.5, True)
    return p


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    rid = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    h = OxmlElement('w:hyperlink'); h.set(qn('r:id'), rid)
    r = OxmlElement('w:r'); rPr = OxmlElement('w:rPr')
    color = OxmlElement('w:color'); color.set(qn('w:val'),'315A7D'); rPr.append(color)
    underline = OxmlElement('w:u'); underline.set(qn('w:val'),'single'); rPr.append(underline)
    r.append(rPr); t = OxmlElement('w:t'); t.text = text; r.append(t); h.append(r)
    paragraph._p.append(h)


def build_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Inches(8.5); sec.page_height = Inches(11)
    sec.top_margin = Inches(0.62); sec.bottom_margin = Inches(0.62)
    sec.left_margin = Inches(0.78); sec.right_margin = Inches(0.78)
    sec.header_distance = Inches(0.2); sec.footer_distance = Inches(0.25)
    styles = doc.styles
    styles['Normal'].font.name = 'Georgia'; styles['Normal'].font.size = Pt(9.4)
    styles['Normal']._element.rPr.rFonts.set(qn('w:ascii'),'Georgia')
    styles['Normal']._element.rPr.rFonts.set(qn('w:hAnsi'),'Georgia')
    footer = sec.footer
    ft = footer.add_table(rows=1, cols=2, width=Inches(6.9))
    ft.columns[0].width=Inches(6.2); ft.columns[1].width=Inches(0.7)
    p=ft.cell(0,0).paragraphs[0]; set_font(p.add_run('Research conducted at the Swarm Alignment Hackathon, November 2026'),7.2,False,True,'Georgia','555555')
    p=ft.cell(0,1).paragraphs[0]; add_page_number(p)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before=Pt(10); title.paragraph_format.space_after=Pt(14)
    pPr=title._p.get_or_add_pPr(); pbdr=OxmlElement('w:pBdr')
    for edge in ('top','bottom'):
        el=OxmlElement(f'w:{edge}'); el.set(qn('w:val'),'single'); el.set(qn('w:sz'),'16' if edge=='top' else '8'); el.set(qn('w:space'),'12'); el.set(qn('w:color'),'000000'); pbdr.append(el)
    pPr.append(pbdr)
    set_font(title.add_run('CASCADE: When Half-Truths Become Collective Certainty'),20,True)
    p=para(doc,'Bianca Sawant',size=11.5,bold=True,align=WD_ALIGN_PARAGRAPH.CENTER,after=1)
    para(doc,'Veermata Jijabai Technological Institute (VJTI), Mumbai',size=10,align=WD_ALIGN_PARAGRAPH.CENTER,after=7)
    para(doc,'With',size=9.5,bold=True,align=WD_ALIGN_PARAGRAPH.CENTER,after=0)
    para(doc,'Apart Research',size=10.5,align=WD_ALIGN_PARAGRAPH.CENTER,after=8)
    para(doc,'Abstract',size=14,bold=True,align=WD_ALIGN_PARAGRAPH.CENTER,after=5,keep=True)
    abstract=("Multi-agent language-model systems can combine distributed evidence, but communication may also erase qualifiers or make a defensible statement easy to misread. We introduce CASCADE, a controlled benchmark and trace framework for studying whether literally true ambiguous or selectively incomplete messages change collective decisions. CASCADE generates hidden-profile tasks from atomic facts and executable decision rules, gives five isolated agents different private evidence, and injects matched clear, ambiguous, or omission-based messages while preserving message lineage and private belief reports. The implemented benchmark contains 40 deterministic draft tasks, with a hash-pinned provisional subset for exploratory runs. In the available live experiment, one task was evaluated with Groq's openai/gpt-oss-120b across independent, full-information, individual-exposure, clear, ambiguous, and omission conditions. All four completed group episodes abstained, and no agent adopted the intended incorrect private answer; therefore no information cascade was observed. Ambiguity nevertheless coincided with a drop in final cited-evidence coverage from 3/3 required facts under clear communication to 1/3 and with the only private belief change, a correct NO becoming UNKNOWN. Omission produced two incorrect public recommendations without corresponding private adoption. These results are descriptive rather than causal, but they demonstrate a reproducible way to distinguish uncertainty amplification, public/private divergence, incorrect consensus, and trace-supported propagation.")
    para(doc,abstract,size=9.2,after=5)
    heading(doc,'1. Introduction')
    para(doc,"Networks of language-model agents are increasingly used to divide work, exchange evidence, and aggregate judgments. Communication can improve reasoning, yet it creates a safety-relevant failure surface: a statement may be literally supportable while its referent or omitted qualifier encourages an unwarranted conclusion. If agents repeat such statements, a group may lose decisive context even when no participant explicitly lies.")
    para(doc,"CASCADE studies this failure mode with controlled hidden-profile decisions. Its motivation echoes the Naro va Kunjaro va episode associated with the Ashwatthama narrative in the Mahabharata: a technically qualified utterance changes action because its decisive qualification is obscured. We use the story only as motivation, not as evidence about modern systems.")
    para(doc,"Our contributions are: (1) a deterministic 40-task draft benchmark with atomic facts, executable ground truth, five private evidence views, and matched message variants; (2) an isolated five-agent runner that records controlled exposure, organic relays, private beliefs, public recommendations, token use, and lineage in validated append-only traces; and (3) an exploratory trace analysis that separates wrong public recommendations from private adoption and finds uncertainty amplification, but no incorrect consensus or information cascade, in the available one-task live comparison.")

    doc.add_page_break()
    heading(doc,'2. Related Work')
    para(doc,"Classical informational-cascade theory defines cascades as choices that follow observed predecessors despite private signals [1,2]. Hidden-profile research shows that groups can fail to pool unshared evidence and overemphasize information already shared [3]. Multi-agent debate has recently been used to improve language-model factuality and reasoning [4], while AI-safety debate frames structured disagreement as a possible oversight mechanism [5]. CASCADE complements this work by manipulating the semantic completeness of one controlled message while retaining deterministic task truth, private evidence boundaries, and event-level lineage. This permits a narrower question than general debate performance: whether a defensible but ambiguous communication produces incorrect private adoption or trace-supported propagation.")
    heading(doc,'3. Methods')
    heading(doc,'3.1 Benchmark and ground truth',2)
    para(doc,"Each synthetic task contains canonical entity IDs, atomic facts, a deterministic all-constraints decision rule, and answers YES, NO, or UNKNOWN. The solver computes ground truth from facts rather than generated labels. The repository contains 40 independently generated draft tasks: 15 referential, 15 selective-omission, 5 scope/quantifier, and 5 temporal tasks. Each has five private evidence views and complete, ambiguous, and selective-omission messages. Mechanical validation covers schema, references, solver consistency, evidence allocation, privacy, uniqueness, and treatment consistency. Semantic review remains provisional; the live traces reported here use one hash-pinned referential task, MB_e8ed46b2e2ce70, whose answer is NO.")
    heading(doc,'3.2 Agent experiment',2)
    para(doc,"Five isolated agents used Groq openai/gpt-oss-120b with temperature 0 and strict JSON Schema output. Each prompt contained only the question, answer options, authorized evidence, and explicitly delivered messages. Agents could report UNKNOWN. The network was fully connected. Round 0 measured private beliefs before communication. In round 1, agent 1 sent one controlled message to agents 2-5 before organic drafts were collected; two synchronous communication rounds followed. Group decisions used a strict majority of all five agents; ties or insufficient support yielded ABSTAIN.")
    para(doc,"Six conditions were implemented: no-communication independent reasoning; one full-information agent; five separate individual ambiguous exposures; and multi-agent clear, ambiguous, and omission treatments. The clear-ambiguous pair held task, evidence allocation, model, topology, sender, timing, and rounds fixed. The live snapshot contained 17 unique records across two run namespaces: 15 completed units and two provider JSON-validation failures. Four of five group episodes completed; eleven of twelve control units completed.")
    heading(doc,'3.3 Measures',2)
    para(doc,"An incorrect group decision is a non-abstaining aggregate that differs from ground truth. Incorrect consensus requires at least four of five final private reports to match the same wrong answer. Incorrect adoption requires an eligible exposed agent to move from correct or UNKNOWN to the intended wrong answer. Cascade-like propagation additionally requires that adopter to relay the interpretation and a distinct downstream recipient to adopt it. Final cited-evidence coverage is the fraction of required fact IDs cited across final private reports; communicated coverage is the fraction included in delivered organic messages. These definitions prevent temporal co-occurrence or a public recommendation alone from being labeled a cascade.")

    doc.add_page_break()
    heading(doc,'4. Results')
    para(doc,"Table 1 summarizes the saved live conditions. All four completed group episodes returned ABSTAIN; wrong group decisions and incorrect consensuses were both 0/4. Across their final private reports, 17/20 were UNKNOWN, 3/20 were correct NO, and none was incorrect YES.")
    cap=para(doc,'Table 1. Condition-level outcomes for task MB_e8ed46b2e2ce70 (ground truth NO). Controls are separate from five-agent group episodes.',size=8.2,bold=True,align=WD_ALIGN_PARAGRAPH.LEFT,after=3,keep=True)
    headers=['Condition','Done / fail','Initial -> final','Group','Changed','Wrong','Coverage']
    rows=[
        ['Independent','1 / 1','U,U,U,NO,U -> same','ABSTAIN','0/5','0','2/3'],
        ['Full information','2 / 0','One full agent -> U','n/a','n/a','0/2','2/3'],
        ['Individual ambiguous','9 / 1','Available pairs stable','n/a','0/9','0/9','n/a'],
        ['Clear','1 / 0','U,U,U,NO,U -> same','ABSTAIN','0/5','0','3/3'],
        ['Ambiguous','1 / 0','U,U,U,NO,U -> all U','ABSTAIN','1/5','0','1/3'],
        ['Omission','1 / 0','U,U,U,NO,U -> same','ABSTAIN','0/5','0','3/3'],
    ]
    table=doc.add_table(rows=1,cols=len(headers)); table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.autofit=False
    widths=[1.25,.65,1.72,.72,.58,.5,.62]
    for i,(cell,h,w) in enumerate(zip(table.rows[0].cells,headers,widths)):
        cell.width=Inches(w); set_cell_shading(cell,'294760'); cell.vertical_alignment=WD_ALIGN_VERTICAL.CENTER; set_cell_margins(cell)
        p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER; set_font(p.add_run(h),7.0,True,False,'Georgia','FFFFFF')
    for ri,row in enumerate(rows):
        cells=table.add_row().cells
        for i,(cell,text,w) in enumerate(zip(cells,row,widths)):
            cell.width=Inches(w); cell.vertical_alignment=WD_ALIGN_VERTICAL.CENTER; set_cell_margins(cell)
            if ri%2: set_cell_shading(cell,'F1F4F6')
            p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.LEFT if i in (0,2) else WD_ALIGN_PARAGRAPH.CENTER
            set_font(p.add_run(text),6.8)
    set_table_borders(table)
    para(doc,"Figure 1 shows the principal non-null observation. Clear and omission retained all three required facts in final citations and organic messages. Under ambiguity, final citations retained one required fact and organic messages carried none; decisive fact F004 disappeared.",size=8.9,before=4,after=3)
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(2)
    p.add_run().add_picture(str(FIGURES/'evidence_coverage.png'),width=Inches(6.35))
    para(doc,'Figure 1. Protocol-defined evidence coverage in the one matched live task. Bars show required facts represented in final citations and organic messages; descriptive n=1.',size=7.7,italic=True,align=WD_ALIGN_PARAGRAPH.LEFT,after=4)
    para(doc,"Omission exposed a different distinction. Agent 2 issued an objectively wrong public YES recommendation while its private report remained UNKNOWN. None of four recipients privately adopted YES at the next probe (0/4). Agent 3 later issued another public YES recommendation while also retaining private UNKNOWN. No event met the cascade-like criterion.",size=8.9)

    doc.add_page_break()
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(2)
    p.add_run().add_picture(str(FIGURES/'agent4_trajectory.png'),width=Inches(6.35))
    para(doc,'Figure 2. Agent 4 private belief by round. Clear and omission preserved correct NO; ambiguity ended in UNKNOWN. Confidence in the ambiguous run declined from 0.9 to 0.7 to 0.5.',size=7.7,italic=True,align=WD_ALIGN_PARAGRAPH.LEFT,after=4)
    para(doc,"Both full-information controls returned UNKNOWN with confidence 0.5 and cited two of three required facts despite receiving complete context. This feasibility result limits treatment interpretation: observed abstention may reflect model integration behavior as well as message condition. Two failed units were explicit HTTP 400 JSON-validation records and were not converted into outcomes.",size=8.9)
    heading(doc,'5. Discussion and Limitations')
    para(doc,"The experiment did not produce the hypothesized incorrect cascade. Instead, it separated evidence loss, private uncertainty, and public recommendation. Ambiguity removed a correct private answer and reduced cited evidence, whereas omission elicited wrong public recommendations that recipients resisted privately. For alignment research, this distinction matters: a communication protocol can degrade collective knowledge without creating false consensus, and public outputs need not reveal private reported beliefs.",size=8.9)
    para(doc,"The evidence covers one provisional task, one model, and one matched treatment repetition, so it supports no statistical or causal generalization. The repeated full-information abstention is a feasibility boundary, and UNKNOWN dominates observed reports. Provider JSON-validation errors produced two preserved failures. RQ3 source influence, interventions, alternative models, and topology robustness were not evaluated.",size=8.9)
    heading(doc,'Future Work',2)
    para(doc,"Next steps are human semantic certification, full-information feasibility gating, additional matched repetitions, and clarification or qualifier-preserving relays. A later randomized RQ3 study could vary source cues while keeping message text fixed.",size=8.9)
    heading(doc,'6. Conclusion')
    para(doc,"CASCADE provides an executable framework for measuring how semantically incomplete communication changes evidence use and collective reports. In the available exploratory trace, ambiguity reduced evidence coverage and converted one correct answer into abstention, while omission generated wrong public recommendations without private adoption. No incorrect consensus or information cascade occurred. Careful lineage and private-belief measurement prevented ordinary message exchange from being overstated as cascade evidence.",size=8.9)
    heading(doc,'Code and Data',2)
    para(doc,'Code repository: [INSERT VERIFIED PUBLIC REPOSITORY URL BEFORE SUBMISSION]',size=8.4,after=1)
    para(doc,'Data and traces: repository paths data/benchmark/ and data/pilot/phase3/.',size=8.4,after=1)
    para(doc,'Reproducibility: configs, schemas, validators, frozen protocol, and append-only JSONL traces are included.',size=8.4,after=2)
    heading(doc,'Author Contributions',2)
    para(doc,'Bianca Sawant designed the study, implemented and tested the benchmark and simulation pipeline with LLM-assisted coding, executed and verified the exploratory experiment, and prepared the manuscript.',size=8.4)

    doc.add_page_break()
    heading(doc,'References')
    refs=[
        ('[1] S. Bikhchandani, D. Hirshleifer, and I. Welch. 1992. A Theory of Fads, Fashion, Custom, and Cultural Change as Informational Cascades. Journal of Political Economy 100(5): 992-1026. ','https://doi.org/10.1086/261849'),
        ('[2] S. Bikhchandani, D. Hirshleifer, O. Tamuz, and I. Welch. 2021. Information Cascades and Social Learning. NBER Working Paper 28887. ','https://doi.org/10.3386/w28887'),
        ('[3] G. Stasser and W. Titus. 1985. Pooling of Unshared Information in Group Decision Making: Biased Information Sampling During Discussion. Journal of Personality and Social Psychology 48(6): 1467-1478. ','https://doi.org/10.1037/0022-3514.48.6.1467'),
        ('[4] Y. Du, S. Li, A. Torralba, J. B. Tenenbaum, and I. Mordatch. 2023. Improving Factuality and Reasoning in Language Models through Multiagent Debate. ','https://arxiv.org/abs/2305.14325'),
        ('[5] G. Irving, P. Christiano, and D. Amodei. 2018. AI Safety via Debate. ','https://arxiv.org/abs/1805.00899'),
    ]
    for lead,url in refs:
        p=para(doc,'',size=9.0,after=6); set_font(p.add_run(lead),9.0); add_hyperlink(p,url,url)

    doc.add_page_break()
    heading(doc,'Limitations and Dual-Use / Ethical Considerations')
    para(doc,"CASCADE studies a dual-use mechanism: ambiguous or selectively incomplete language can reveal vulnerabilities in evidence aggregation, but the same knowledge could be used to design manipulative messages. The benchmark mitigates this risk through synthetic organizations and decisions, explicit provenance, deterministic ground truth, and separation of truthful ambiguity from falsehood. Results should be used to improve qualifier preservation, clarification, and abstention policies rather than optimize persuasion.")
    para(doc,"The study does not involve personal data or real-world reputational claims. Future releases should retain fictional scenarios, document semantic review, avoid operational guidance for deception, and report null findings and failures alongside positive effects. The current task pool is provisional; the one-task live observation should not be used to characterize deployed systems.")
    heading(doc,'Additional Trace Details',2)
    para(doc,"Ambiguous agent 4: event 8 NO (0.9), event 26 NO (0.7), event 45 UNKNOWN (0.5). Omission agent 2's wrong public YES at message event 17 had zero private adopters among four recipients at their next probes. Agent 3's later public YES at event 34 cited the controlled message, not event 17, and its private belief remained UNKNOWN. All five episode records passed 2,403 trace cross-reference checks, including the explicit failed record.")
    heading(doc,'Project Provenance',2)
    para(doc,"The reported benchmark, runner, and trace analysis are the CASCADE artifacts evaluated here; archived legacy candidate audits are excluded from the active benchmark. Exact dates of any preparatory repository scaffolding were not independently established, so this paper makes no claim that every code artifact originated during the event.")
    heading(doc,'LLM Usage Statement')
    para(doc,"LLM assistance was used for code generation, debugging, trace summarization, figure preparation, and manuscript drafting. The author directed the research design and reviewed empirical claims against deterministic task records and saved event traces. No LLM-generated label was used as benchmark ground truth, and no new inference was performed to create the reported results.")
    doc.core_properties.title='CASCADE When Half Truths Become Collective Certainty'
    doc.core_properties.author='Bianca Sawant'
    doc.core_properties.subject='Apart Research Swarm Alignment Hackathon Track 2 submission'
    doc.core_properties.keywords='multi-agent systems, ambiguity, information cascades, hidden profiles, alignment'
    doc.save(DOCX)


if __name__ == '__main__':
    make_coverage_figure(FIGURES/'evidence_coverage.png')
    make_trajectory_figure(FIGURES/'agent4_trajectory.png')
    build_doc()
    print(DOCX)
