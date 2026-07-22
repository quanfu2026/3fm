import os
from docx import Document

def extract_from_multiple_files(file_list, output_txt_path):
    """
    讀取多個 Word 檔案，自動抓取【標準客服回答 (Ground Truth)】的內容，
    並自動剔除重複的段落，整合輸出為 RAG 系統的知識庫（課本）。
    """
    unique_specs = set() 
    
    print("🚀 開始批量從問答集中萃取『知識庫課本』...")
    print("-" * 50)
    
    for docx_path in file_list:
        if not os.path.exists(docx_path):
            print(f"⚠️ 找不到檔案：{docx_path}，已跳過該檔案。")
            continue
            
        print(f"📖 正在讀取並解析：{docx_path} ...")
        try:
            doc = Document(docx_path)
        except Exception as e:
            print(f"❌ 檔案 {docx_path} 讀取失敗: {e}")
            continue
            
        current_gt = ""
        is_gt_block = False
        
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
                
            # 1. 識別標準回答的開頭
            if text.startswith("【標準客服回答 (Ground Truth)】"):
                is_gt_block = True
                gt_content = text.replace("【標準客服回答 (Ground Truth)】", "").strip()
                if gt_content:
                    current_gt = gt_content
                continue
                
            # 2. 識別結束（遇到下一個樣本或提問）
            if text.startswith("樣本 ID:") or text.startswith("樣本 ID：") or text.startswith("【客戶提問"):
                if is_gt_block and current_gt.strip():
                    unique_specs.add(current_gt.strip())
                is_gt_block = False
                current_gt = ""
                continue
                
            # 3. 處理跨行的標準回答內容
            if is_gt_block:
                if current_gt:
                    current_gt += "\n" + text
                else:
                    current_gt = text

        # 檢查檔案結尾
        if is_gt_block and current_gt.strip():
            unique_specs.add(current_gt.strip())

    # 4. 寫出成唯一的總知識庫文字檔
    with open(output_txt_path, "w", encoding="utf-8") as f:
        for idx, spec in enumerate(sorted(list(unique_specs)), 1):
            f.write(f"=== 產品知識資料編號 {idx} ===\n")
            f.write(spec + "\n\n")
            
    print("-" * 50)
    print("🎉 總知識庫（課本資料）建置完成！")
    print(f"📊 5 個子集檔案總計萃取出 {len(unique_specs)} 筆核心知識與保固規範。")
    print(f"💾 乾淨的知識庫檔案已成功儲存至：{output_txt_path}")
    print("=" * 50)

if __name__ == "__main__":
    my_5_subsets = [
        "knowledge_base/evaluation/智慧家電與廚房電器類客服問答集_100筆.docx",
        "knowledge_base/evaluation/智慧家電類客服問答集_100筆.docx",
        "knowledge_base/evaluation/服飾類客服問答集_100筆.docx",
        "knowledge_base/evaluation/汽車百貨類客服問答集_100筆.docx",
        "knowledge_base/evaluation/服務保固類客服問答集_100筆.docx",
        "knowledge_base/evaluation/掃地機器人App客服問答集_100筆.docx",
        "knowledge_base/evaluation/電商客服問答集.docx"
    ]
    
    output_kb_file = "knowledge_base/docs/product_specs.txt"
    os.makedirs(os.path.dirname(output_kb_file), exist_ok=True)
    
    extract_from_multiple_files(my_5_subsets, output_kb_file)