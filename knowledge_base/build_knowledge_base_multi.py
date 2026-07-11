import os
from docx import Document

def extract_from_multiple_files(file_list, output_txt_path):
    """
    讀取多個 Word 檔案，自動抓取『輸入的商品規格說明：』後方的純產品規格，
    並使用 set 資料結構自動剔除重複的規格內容，最終整合輸出為系統的知識庫（課本）。
    """
    unique_specs = set() # 使用 set 自動過濾 5 個檔案中所有重複的規格
    
    print("🚀 開始批量萃取 5 個子集的『產品規格說明書』...")
    print("-" * 50)
    
    for docx_path in file_list:
        if not os.path.exists(docx_path):
            print(f"⚠️ 找不到檔案：{docx_path}，已跳過該檔案。")
            continue
            
        print(f"📖 正在讀取並解析：{docx_path} ...")
        try:
            doc = Document(docx_path)
        except Exception as e:
            print(f"❌ 檔案 {docx_path} 讀取失敗，錯誤原因: {e}")
            continue
            
        current_spec = ""
        is_spec_block = False
        
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
                
            # 1. 識別規格說明的開頭標籤
            if text.startswith("輸入的商品規格說明：") or text.startswith("輸入的商品規格說明:"):
                is_spec_block = True
                # 擷取同行的後續文字，並移除常見引號
                spec_content = text.replace("輸入的商品規格說明：", "").replace("輸入的商品規格說明:", "").strip()
                spec_content = spec_content.strip("「」"'")
                if spec_content:
                    current_spec = spec_content
                continue
                
            # 2. 識別區塊結束標籤（當遇到 QA 對、樣本 ID 或客戶提問時，代表目前的規格區塊結束）
            if (text.startswith("LLM 模擬生成的 QA 對") or 
                text.startswith("樣本 ID:") or 
                text.startswith("樣本 ID：") or 
                text.startswith("【客戶提問") or 
                text.startswith("【標準客服回答")):
                
                if is_spec_block and current_spec.strip():
                    unique_specs.add(current_spec.strip())
                is_spec_block = False
                current_spec = ""
                continue
                
            # 3. 如果處於規格區塊中且是跨行文字，則持續進行累加
            if is_spec_block:
                current_spec += "\n" + text.strip("「」"'")

        # 檢查每一份檔案結尾是否還有未寫入的規格
        if is_spec_block and current_spec.strip():
            unique_specs.add(current_spec.strip())

    # 4. 將所有去重複後的純規格說明，寫出成唯一的總知識庫文字檔 (即 RAG 的純產品課本)
    with open(output_txt_path, "w", encoding="utf-8") as f:
        for idx, spec in enumerate(sorted(list(unique_specs)), 1):
            f.write(f"=== 產品資料編號 {idx} ===\n")
            f.write(spec + "\n\n")
            
    print("-" * 50)
    print("🎉 總知識庫（課本資料）建置完成！")
    print(f"📊 5 個子集檔案總計萃取出 {len(unique_specs)} 筆『不重複』的純產品規格說明。")
    print(f"💾 乾淨的知識庫檔案已成功儲存至：{output_txt_path}")
    print("=" * 50)

if __name__ == "__main__":
    # ========================================================
    # 📌 請在這裡填入您那 5 個子集 Word 檔案的真實名稱
    # ========================================================
    my_5_subsets = [
        "3C科技類客服問答集_100筆.docx",
        "智慧家電類客服問答集_100筆.docx",
        "服飾類客服問答集_100筆.docx",
        "汽車百貨類客服問答集_100筆.docx",
        "服務保固類客服問答集_100筆.docx"
    ]
    
    # 輸出的總知識庫純文字檔名
    output_kb_file = "電商產品規格知識庫_課本.txt"
    
    # 執行批量合併與去重萃取
    extract_from_multiple_files(my_5_subsets, output_kb_file)
