import logging
from result import Result

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


WELLCOME = -2
INTRO    = -1
Q1       =  0
Q2       =  1
Q3       =  2
Q4       =  3
Q5       =  4
Q6       =  5
Q7       =  6
Q8       =  7
Q9       =  8
Q10      =  9
Q11      = 10
Q12      = 11
Q13      = 12
Q14      = 13
Q15      = 14


class Status:
    def __init__(self, current_item = WELLCOME, t_ini = 0.0, t_end = 0.0, t_ini_q = 0.0, results = [], final_score = 0, status = None):
        if status:
            self.current_item = int(status['current_item'])
            self.t_ini_q      = float(status['t_ini_q'])    
            self.t_ini        = float(status['t_ini'])      
            self.t_end        = float(status['t_end'])      
            self.final_score  = int(status['final_score'])
            self.results      = [Result(result = res) for res in status['results']]
        else:
            self.current_item               = current_item
            self.t_ini_q                    = t_ini_q
            self.t_ini                      = t_ini
            self.t_end                      = t_end
            self.final_score                = final_score
            self.results                    = [Result(item = i) for i in range(15)]
    
    def to_dict(self):
        return {
            'current_item' : self.current_item,
            't_ini_q'      : str(self.t_ini_q),
            't_ini'        : str(self.t_ini),
            't_end'        : str(self.t_end),
            'final_score'  : self.final_score,
            'results'      : [res.to_dict() for res in self.results]
            }
