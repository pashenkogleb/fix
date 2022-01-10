import quickfix
import xml.etree.ElementTree as ET
import pandas as pd
import tqdm
import numpy as np
import queue


DEFAULT_XML = "my_FIX44.xml"

TRADE_FEED = "qf_log/FIX.4.4-MU9051500001-IFIX-EQ-UAT.messages.current.log"
TC_FEED = "qf_log/FIX.4.4-MU9051500002-IFIX-TC-EQ-UAT.messages.current.log"
DC_FEED = "qf_log/FIX.4.4-MU9051500004-IFIX-DC-EQ-UAT.messages.current.log" #drop copy ffed



def tag_dict(xml_name = DEFAULT_XML):
    '''
    returns dict from XML definition
    '''
    root = ET.parse(xml_name)
    return {x.attrib['number'] : x.attrib['name'] for x in  root.find("fields")}

def msg_types(xml_name = DEFAULT_XML):
    '''
    returns dataframe with message descriptions
    '''
    root = ET.parse(xml_name)
    msg_fr = [(x.attrib['name'], x.attrib['msgtype'], x.attrib['msgcat']) for x in  root.find("messages")]
    res = pd.DataFrame(msg_fr, columns = ['name','msgtype','msgcat'])
    res['msgtype'] = res['msgtype'].astype(str)
    return res


def parse_msg_part(root, msg_part, mapping):
    '''
    parses msg part, like header
    '''
    rel = root.find(msg_part)
    res =[]
    group_count = 0
    # to_parse = []
    # to_check  = queue.Queue()
    # for x in rel:
    #     to_check.put(x)
    # while True:
    #     try:
    #         el = to_check.get()
    #     except queue.Empty:
    #         break
    #     if el.tag == "group":
    #         for x in el:
    #             to_check.put(x)
    #     elif el.tag == "field":


    for x in rel:
        if x.tag == "group":
            for group_field in x:
                if group_field.tag == "group": #stupidest way to handle nested groups
                    group_count+=1
                    for group_field2 in group_field:
                        res.append((group_field2.attrib['number'],mapping[group_field2.attrib['number']], group_field2.text, group_count))
                    group_count+=1
                else:        
                    res.append((group_field.attrib['number'],mapping[group_field.attrib['number']], group_field.text, group_count))
            group_count +=1
        elif x.tag == "field":
            res.append((x.attrib['number'],mapping[x.attrib['number']], x.text, np.nan))
        else:
            raise ValueError("unknown tag" + x.tag)  
        
    fr  = pd.DataFrame(res, columns = ['key','key_str', 'val', "group_id"])
    fr['msg_part'] = msg_part
    
    return fr

def parse_msg(raw_msg, xml_name =DEFAULT_XML, data_dictionary = None, field_dict = None, msg_fr = None):
    '''
    to speed up can pass data_dictionary, field_dict and msg_type
    '''
    if data_dictionary is None:
        data_dictionary  = quickfix.DataDictionary(xml_name)
    if field_dict is None:
        field_dict = tag_dict(xml_name)
    if msg_fr is None:
        msg_fr = msg_types(xml_name)

    if isinstance(raw_msg,str):
        msg = quickfix.Message(raw_msg, data_dictionary, True)
    else:
        msg =raw_msg 
    assert isinstance(msg, quickfix.Message)
    root = ET.fromstring(msg.toXML())
    
    fr1 = parse_msg_part(root, "header",field_dict)
    fr2 = parse_msg_part(root, "body",field_dict)
    fr3 = parse_msg_part(root, "trailer",field_dict)

    df = pd.concat([fr1,fr2,fr3], ignore_index=True)
    if len(df)==0:
        return df
    df["msgtype"] = df['val'][df['key_str']=="MsgType"].iloc[0]
    df['msgtype'] = df['msgtype'].astype(str)
    df["msg_time"] = pd.to_datetime(df['val'][df['key_str']=="SendingTime"].iloc[0])
    df['sender'] = df['val'][df['key_str']=="SenderCompID"].iloc[0]
    df = pd.merge(df,msg_fr, how='left', on=['msgtype'])

    #assert df['key'].nunique() == len(df), "{}:{}".format(df['key'].nunique(), len(df)) # I do not handle repeating groups, so make sure that there is none of such shit

    return df


def msg_frame_to_str(fr):
    ''''
    TODO: currently ignores msg groups, make sense to put them together somehow
    '''
    msgcat =  fr['msgcat'].iloc[0]
    msgname = fr['name'].iloc[0]

    msgbody = "|".join([f"{k}={v}" for k,v in zip(fr['key_str'],fr['val'])])

    return f"{msgname}({msgcat}): {msgbody}"


def get_messages(path, xml_name = DEFAULT_XML):
    '''
    converts string line to separate message frame 
    '''
    data_dictionary  = quickfix.DataDictionary(xml_name)
    field_dict = tag_dict(xml_name)
    msg_fr = msg_types(xml_name)

    with open(path) as f:
        msgs = f.read()
        
    msgs_long = msgs.splitlines()
    timestamps =[x[:27] for x in msgs_long]
    msgs=[x[30:] for x in msgs_long]
    frames =[]


    for i, msg in tqdm.tqdm(enumerate(msgs), total = len(msgs)):
        fr = parse_msg(msg, 
        data_dictionary = data_dictionary,field_dict = field_dict, msg_fr = msg_fr
        )

        fr['msg_num'] = i
        fr['msg_timestamp'] = pd.to_datetime(timestamps[i])

        frames.append(fr)
    df = pd.concat(frames,ignore_index=True)
    return df

def pivot_msgtype(df):
    '''
    pivots messages of same type
    '''
    assert df['msgtype'].nunique(), "have to be all of same type"
    fr = df.copy()
    msg_info = fr.groupby('msg_num')[['msg_time','msg_timestamp']].first()


    fr['adjkey'] =np.where(fr['group_id'].notna(), fr['key_str']  + fr['group_id'].fillna(-1).astype(int).astype(str), fr['key_str'])
    ordering = fr['adjkey'].unique()
    
    res =  fr.pivot('msg_num',"adjkey", 'val')[ordering]
    res = pd.concat([msg_info,res],axis=1)

    #res[msg_info.columns] = msg_info.loc[res.index, :]
    return res
