import os
from docx import Document

def extract_from_multiple_files(file_list, output_txt_path):
    unique_specs = set() # 使用 set 自動過濾 5 個檔案中所有重複的規格
    
    print("🚀 開始批量萃取 5 個子集的『產品規格說明書』...")
    print("-" * 40)
    
    for docx_path in file_list:
        if not os.path.exists(docx_path):
            print(f"⚠️ 找不到檔案：{docx_path}，跳過此檔案。")
            continue
            
        print(f"📖 正在讀取：{docx_path} ...")
        doc = Document(docx_path)
        current_spec = ""
        is_spec_block = False
        
        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
                
            if text.startswith("輸入的商品規格說明："):
                is_spec_block = True
                spec_content = text.replace("輸入的商品規格說明：", "").strip()
                spec_content = spec_content.strip("「」\"'")
                if spec_content:
                    current_spec = spec_content
                continue
                
            if text.startswith("LLM 模擬生成的 QA 對：") or text.startswith("樣本 ID:") or text.startswith("【客戶提問"):
                if is_spec_block and current_spec:
                    unique_specs.add(current_spec)
                is_spec_block = False
                current_spec = ""
                continue
                
            if is_spec_block:
                current_spec += "\n" + text.strip("「」\"'")

        if is_spec_block and current_spec:
            unique_specs.add(current_spec)

    # 寫出成唯一的總知識庫文字檔
    with open(output_txt_path, "w", encoding="utf-8") as f:
        for idx, spec in enumerate(unique_specs, 1):
            f.write(f"=== 產品資料編號 {idx} ===\n")
            f.write(spec + "\n\n")
            
    print("=" * 40)
    print(f"🎉 總知識庫（課本）建置完成！")
    print(f"📊 5 個檔案總計萃取出 {len(unique_specs)} 筆不重複的純產品規格說明。")
    print(f"💾 檔案已儲存至：{output_txt_path}")
    print("=" * 40)

if __name__ == "__main__":
    # 📌 【在引號內填入你 5 個子集的真正 Word 檔名】
    my_5_subsets = [
        "3C科技類客服問答集_100筆.docx",
        "智慧家電類客服問答集_100筆.docx",
        "服飾類客服問答集_100筆.docx",
        "汽車百貨類客服問答集_100筆.docx",
        "服務保固類客服問答集_100筆.docx"
    ]
    
    output_kb_file = "電商產品規格知識庫_課本.txt"
    
    # 執行批量合併萃取
    extract_from_multiple_files(my_5_subsets, output_kb_file)