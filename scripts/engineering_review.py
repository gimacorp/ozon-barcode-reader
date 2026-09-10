"""Допуски, контраст, геометрия дна и численное масштабирование."""
from pathlib import Path
import sys,json,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from barcode_reader.engineering import load_config,summarize,working_distance,depth_of_field
from barcode_reader.geometry import evaluate_label_focus,evaluate_end_face
from barcode_reader.optics import contrast

def run():
    c=load_config();line=[]
    # Суммы абсолютных вкладов: смещение, размер, угол, деформация, настройка.
    for face,fov in [('top',700),('bottom',700),('left',450),('right',450)]:
        wd=working_distance(28,8192*.0035,fov);near,far=depth_of_field(28,8,.007,wd)
        terms=({'height':5,'pitch':300*math.sin(math.radians(.5)),'roll':200*math.sin(math.radians(.5)),'warp':2,'focus_setup':1}
            if face=='top' else {'sag':2,'belt_runout':1,'focus_setup':1} if face=='bottom' else
            {'center':3,'half_width':2,'yaw':300*math.sin(math.radians(.5)),'roll':200*math.sin(math.radians(.5)),'warp':1,'focus_setup':1})
        budget=sum(terms.values());line.append({'face':face,'wd_mm':wd,'near_mm':near,'far_mm':far,'terms_mm':terms,
            'max_deviation_mm':budget,'remaining_near_margin_mm':wd-near-budget,'remaining_far_margin_mm':far-wd-budget})
    speeds=[]
    for v in [1000,1500,2000]:
        cc=c|{'speed_mm_s':v};e=summarize(cc)
        speeds.append({'speed_m_s':v/1000,'budget_ms':e['remaining_processing_delivery_s']*1000,
                       'whole_label':evaluate_label_focus(cc)['min_whole_label_coverage'],
                       'two_frames':evaluate_label_focus(cc,required_frames=2)['min_whole_label_coverage'],
                       'fps_same_step':16*v/1000})
    sizes=[]
    for name,changes in [('X=0.20',{'min_module_mm':.2}),('800x500x500',{'box_length_mm':800.,'box_width_mm':500.,'box_height_mm':500.})]:
        cc=c|changes;e=summarize(cc);g=evaluate_end_face(cc)
        sizes.append({'scenario':name,'line_px_module':e['line_px_module_horizontal'],'end_px_module':g['min_best_px_per_module'],
                      'budget_ms':e['remaining_processing_delivery_s']*1000,'side_fov_margin_mm':(450-cc['box_height_mm'])/2,
                      'whole_label':evaluate_label_focus(cc)['min_whole_label_coverage']})
    # Верхние касательные ножевых носиков ±10 мм, R=3 мм. Чистый просвет 14 мм.
    # Проверяем каждый луч из краёв источников на прогибе 0...2 мм против окружностей.
    import numpy as np
    clearance=[]
    for sag in np.linspace(0,2,21):
        target=np.array([0.,-sag])
        for sx in [-67.5,-42.5,42.5,67.5,-1.75,1.75]:
            source=np.array([sx,-180. if abs(sx)>2 else -712.])
            ray=source-target
            for cx in [-10.,10.]:
                center=np.array([cx,-3.]);t=np.clip((center-target)@ray/(ray@ray),0,1)
                clearance.append(float(np.linalg.norm(target+t*ray-center)-3))
    result={'line_focus':line,'tolerances':{'center_mm':3,'width_mm':4,'height_mm':5,'yaw_deg':.5,'pitch_roll_deg':.5,
        'side_warp_mm':1,'top_warp_mm':2,'bottom_sag_mm':2,'trigger_position_error_mm':1},
        'end_contrast':contrast(),'speeds':speeds,'sizes':sizes,
        'bottom':{'nose_radius_mm':3,'top_tangent_gap_mm':20,'minimum_clear_gap_mm':14,'window_clear_width_mm':50,
            'window_z_mm':-30,'light_centers_x_mm':[-55,55],'light_z_mm':-180,'emitter_width_mm':25,
            'min_ray_roller_clearance_mm':min(clearance),'worst_sag_mm':2,
            'note':'Проверка идеальных лучей в продольном разрезе. Прочность картона, высота носиков и паразитные блики проверяются приёмкой.'},
        'transfer':{'frame_MB':65.408,'wire_min_ms':65.408*8/10,'budget_ms':80,
                    'deadline_after_last_exposure_ms':635,'processing_from_exposure_ms':500,'decode_queue_budget_ms':420,'delivery_ms':50},
        'lens_precision':'Расстояния от главной плоскости тонкой линзы; фокусировку на стенде измерять по контрасту. Для LD эффективное f=28.65 мм.'}
    (ROOT/'results/engineering_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
