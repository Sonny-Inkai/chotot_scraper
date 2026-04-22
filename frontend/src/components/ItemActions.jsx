import React from 'react';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import { formatPrice, formatAdjustedTime } from './itemUtils';

const ItemActions = ({ items, selectedItems, setSelectedItems, filters }) => {
  const queryClient = useQueryClient();

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedItems(new Set(items.map(item => item._id)));
    } else {
      setSelectedItems(new Set());
    }
  };

  const handleGetPrompt = () => {
    const selectedItemsData = items.filter(item => selectedItems.has(item._id));

    if (selectedItemsData.length === 0) {
      alert('Vui lòng chọn ít nhất một sản phẩm để tạo prompt.');
      return;
    }

    const promptIntro = `**ROLE:** Bạn là một Chuyên gia Thẩm định Sản phẩm Công nghệ Cũ dày dạn kinh nghiệm tại thị trường Việt Nam, với biệt tài săn "KÈO THƠM" và có sự am hiểu sâu sắc về các dòng sản phẩm, biến động giá, tâm lý người mua/bán và các rủi ro đặc thù tại Việt Nam.`;

    const promptConclusion = `
**ROLE:** Bạn là "Thợ Săn Hàng Cũ" (Flipping Expert), THANH KHOẢN expert thực chiến tại Việt Nam. Tiêu chí của bạn là CHẬM MÀ CHẮC: Chỉ săn "KÈO THƠM" có rủi ro cực thấp, mua rẻ bán đắt, thanh khoản siêu nhanh (bay trong 3-7 ngày). 

**MISSION:** Đánh giá danh sách tin đăng Chợ Tốt/FB. Lọc bỏ toàn bộ rác, hàng ngáo giá, hàng rủi ro cao. CHỈ GIỮ LẠI kèo thực sự ngon ăn. 
NGUYÊN TẮC VÀNG: "Thà bỏ lỡ 100 kèo bình thường, còn hơn ôm 1 kèo xịt làm giam vốn".

**BỘ LỌC TỬ THẦN (ĐÁNH TYPE 2 NGAY LẬP TỨC NẾU DÍNH 1 TRONG CÁC LỖI SAU):**
2. **Ngáo giá:** Giá rao bán bằng hoặc cao hơn giá THU MUA CỦA THỢ đối với đồ cũ cùng tình trạng. 
3. **Lợi nhuận mỏng:** Tiềm năng chênh lệch giá (mua vào - bán ra) dưới 300.000 VNĐ. Không bõ công đi lại và dọn dẹp máy.
4. **Hàng rác / Lỗi chức năng nặng:** Có chữ "bán xác", "lỗi nhẹ", "sọc màn", "hư main", "mất FaceID", "dính iCloud", "hỏng hóc", "chữa cháy".
5. **Cửa hàng / Thợ thuyền:** Lời văn sặc mùi con buôn, chụp ảnh tại cửa hàng, có bảo hành shop, nhiều icon lòe loẹt.

**TIÊU CHÍ "KÈO THƠM" (CHỈ ĐÁNH TYPE 1 KHI ĐẠT ĐỦ ĐIỀU KIỆN):**
1. **Giá "Sập Sàn" (Quan trọng nhất):** Giá phải thấp hơn thị trường ĐỒ CŨ ít nhất 25-30% (hoặc rẻ hơn thị trường ít nhất 500k-1 triệu tùy giá trị máy). 
2. **Thanh khoản.
4. **Hồ sơ:** Người dùng cá nhân thanh lý gấp (chuyển nhà, lên đời, kẹt tiền).

**YÊU CẦU OUTPUT BẮT BUỘC:**
- BẮT BUỘC trả về đánh giá cho TOÀN BỘ _id có trong danh sách input. Không được bỏ sót bất kỳ _id nào.
- Chỉ trả về 1 mảng JSON Array hợp lệ. KHÔNG text thừa, KHÔNG giải thích ngoài JSON.
- Luôn suy nghĩ về THANH KHOẢNx3.14, DÒNG TIỀN để quyết định nên mua sản phẩm đó hay không. 
- Sử dụng Google Search để tìm kiếm thông tin về sản phẩm, thị trường, giá cả, ... ví dụ "Thông tin sản phẩm + facebook" xem bài đăng đó nhiều tương tác, mọi người muốn mua sản phẩm đó nhiều không, thanh khoản thế nào.
- Sản phẩm cũ đó phải rẻ hơn so với mặt bằng trung bình chính nó tại thị trường đồ cũ. Khi tôi mua vào, và bán ra thì giá bán ra đó vẫn phải thấp hơn so với giá thị trường thì mới hấp dẫn và thanh khoản cao, nhưng biên độ lợi nhuận vẫn đảm bảo.

Định dạng JSON:
[
  {
    "_id": "<giữ nguyên _id gốc>",
    "type": 1, 
    "buy_price": <Số nguyên, VD: 750000. Giá chốt thực tế bạn sẽ nhắn tin mặc cả với người bán>,
    "sell_price": <Số nguyên, VD: 1200000. Giá bán ra dự kiến (phải thực tế, dễ bay trong 1 tuần)>,
    "new_title": "Tên món hàng tối ưu SEO để đăng bán lại nhanh",
    "note": "PHÂN TÍCH NGẮN: 1. Giá TT món này cũ khoảng bao nhiêu. 2. Tại sao giá này là hời? 3. Mẹo chat để ép giá xuống mức buy_price."
  },
  {
    "_id": "<giữ nguyên _id gốc>",
    "type": 2 // TỪ CHỐI MUA (Rác, giá cao, quá xa, rủi ro, cửa hàng...)
  }
]
`;
    const itemDataStrings = selectedItemsData.map((item, index) => {
        const getSafe = (obj, path, defaultValue = null) => {
            const keys = Array.isArray(path) ? path : path.replace(/\[(\w+)\]/g, '.$1').replace(/^\./, '').split('.');
            let result = obj;
            for (const key of keys) {
                if (result === null || typeof result !== 'object') return defaultValue;
                result = result[key];
                if (result === undefined) return defaultValue;
            }
            return result;
        };

        let detailsString = `--- Thông tin Sản phẩm ${index + 1} ---\n`;

        const id = getSafe(item, '_id');
        if (id !== null) detailsString += `- ID Sản Phẩm: "${id}"\n`;
        
        const category = getSafe(item, 'category_name');
        if (category) detailsString += `- Loại Sản Phẩm: ${category}\n`;
        
        const accountName = getSafe(item, 'account_name');
        if (accountName) detailsString += `- Tên Người Bán: ${accountName}\n`;
        
        const subject = getSafe(item, 'subject');
        if (subject) detailsString += `- Tiêu Đề bài đăng: ${subject}\n`;

        const body = getSafe(item, 'body');
        if (body) {
            detailsString += `- Mô Tả của người bán: ${body.replace(/\n+/g, ' ')}\n`;
        }
        
        const price = getSafe(item, 'price');
        if (price) detailsString += `- Giá được người bán đăng: ${formatPrice(price)}\n`;
        
        const listTime = getSafe(item, 'list_time');
        if (listTime) detailsString += `- Thời Gian từ lúc đăng: ${formatAdjustedTime(listTime)}\n`;

        const params = getSafe(item, 'params');
        if (Array.isArray(params) && params.length > 0) {
            detailsString += `- Thông Tin Chi Tiết Của Sản Phẩm:\n`;
            params.forEach(param => {
                detailsString += `  ${param.label}: ${param.value}\n`;
            });
        }
          
        return detailsString.trim();
    }).join('\n\n');

    const finalPrompt = `${promptIntro}\n\nHãy đánh giá các sản phẩm có thông tin chi tiết như sau:\n\n${promptConclusion}\n\nDanh sách các sản phẩm:\n\n${itemDataStrings}`;

    navigator.clipboard.writeText(finalPrompt);
    
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = `Prompt đã được tạo và sao chép cho ${selectedItemsData.length} sản phẩm!`;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, 3000);
  };

  const handleDeleteSelected = async () => {
    if (selectedItems.size === 0) {
      alert('Vui lòng chọn ít nhất một sản phẩm để xóa.');
      return;
    }

    const confirmed = window.confirm(`Bạn có chắc chắn muốn xóa ${selectedItems.size} sản phẩm đã chọn?`);
    if (!confirmed) return;

    try {
      const response = await axios.delete(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/items`, {
        data: { itemIds: Array.from(selectedItems) }
      });

      if (response.data.success) {
        queryClient.invalidateQueries({ queryKey: ['items'] });
        setSelectedItems(new Set());
        alert(`Đã xóa thành công ${response.data.deletedCount} sản phẩm.`);
      }
    } catch (error) {
      console.error('Error deleting items:', error);
      alert('Đã xảy ra lỗi khi xóa sản phẩm: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleDeleteFiltered = async () => {
    const filterCount = items.length;
    if (filterCount === 0) {
      alert('Không có sản phẩm nào thỏa mãn điều kiện lọc.');
      return;
    }

    const confirmed = window.confirm(`Bạn có chắc chắn muốn xóa tất cả ${filterCount} sản phẩm đang hiển thị theo điều kiện lọc hiện tại?`);
    if (!confirmed) return;

    try {
      const filterParams = { ...filters };
      delete filterParams.page;
      delete filterParams.sortBy;
      
      if (filterParams.itemIds) {
        filterParams.itemIds = filterParams.itemIds.split(',')
          .map(id => id.trim())
          .filter(id => id !== '')
          .join(',');
      }
      
      Object.keys(filterParams).forEach(key => {
        if (filterParams[key] === '') {
          delete filterParams[key];
        }
      });

      const response = await axios.delete(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/items/filtered`, {
        params: filterParams
      });

      if (response.data.success) {
        queryClient.invalidateQueries({ queryKey: ['items'] });
        alert(`Đã xóa thành công ${response.data.deletedCount} sản phẩm.`);
      }
    } catch (error) {
      console.error('Error deleting filtered items:', error);
      alert('Đã xảy ra lỗi khi xóa sản phẩm: ' + (error.response?.data?.error || error.message));
    }
  };

  return (
    <div className="header">
      <div className="select-all">
        <input
          type="checkbox"
          onChange={handleSelectAll}
          checked={selectedItems.size === items.length && items.length > 0}
        />
        <span>Chọn tất cả</span>
      </div>
      <div className="header-buttons">
        <button onClick={handleGetPrompt} className="get-prompt-btn">
          Get Prompt
        </button>
        <button onClick={handleDeleteSelected} className="delete-selected-btn">
          Xóa
        </button>
        <button onClick={handleDeleteFiltered} className="delete-filtered-btn">
          Xóa Theo Filter
        </button>
      </div>
    </div>
  );
};

export default ItemActions;