// 全局状态变量
let currentPattern = null;  // 当前生成的图案
let currentSteps = null;    // 当前的剪纸步骤
let viewMode = 'visualization';  // 视图模式：'visualization'可视化, 'svg'SVG
let isCutting = false;      // 切割状态
let isPaused = false;       // 暂停状态
let currentView = 'pattern'; // 当前视图状态
let currentStepIndex = 0;    // 当前步骤索引
let currentSVG = null;       // 当前的SVG数据
let currentVisualization = null; // 当前的可视化图像

/**
 * 显示提示消息
 * @param {string} message - 要显示的消息
 * @param {string} type - 消息类型：'success'成功, 'danger'错误, 'warning'警告
 */
function showMessage(message, type = 'success') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    document.body.appendChild(alert);
    
    // 3秒后自动消失
    setTimeout(() => {
        alert.classList.add('hide');
        setTimeout(() => alert.remove(), 300);
    }, 3000);
}

/**
 * 显示确认对话框
 * @param {string} message - 确认消息
 * @param {Function} onConfirm - 确认回调函数
 * @param {Function} onCancel - 取消回调函数
 */
function showConfirmModal(message, onConfirm, onCancel) {
    const modal = document.getElementById('confirmModal');
    const modalText = document.getElementById('confirmModalText');
    const confirmBtn = modal.querySelector('button[onclick="confirmOperation()"]');
    const cancelBtn = modal.querySelector('button[onclick="cancelOperation()"]');
    
    modalText.textContent = message;
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('show'), 10);
    
    // 存储回调函数
    modal.dataset.onConfirm = onConfirm;
    modal.dataset.onCancel = onCancel;
}

/**
 * 确认操作
 */
window.confirmOperation = function() {
    const modal = document.getElementById('confirmModal');
    const onConfirm = modal.dataset.onConfirm;
    
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
        if (typeof onConfirm === 'function') {
            onConfirm();
        }
    }, 300);
}

/**
 * 取消操作
 */
window.cancelOperation = function() {
    const modal = document.getElementById('confirmModal');
    const onCancel = modal.dataset.onCancel;
    
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
        if (typeof onCancel === 'function') {
            onCancel();
        }
    }, 300);
}

/**
 * 显示错误对话框
 * @param {string} message - 错误消息
 */
function showErrorModal(message) {
    const modal = document.getElementById('errorModal');
    const modalText = document.getElementById('errorModalText');
    
    modalText.textContent = message;
    modal.style.display = 'flex';
    setTimeout(() => modal.classList.add('show'), 10);
}

/**
 * 关闭错误对话框
 */
window.closeErrorModal = function() {
    const modal = document.getElementById('errorModal');
    modal.classList.remove('show');
    setTimeout(() => modal.style.display = 'none', 300);
}

/**
 * 设置按钮状态
 * @param {HTMLElement} button - 目标按钮元素
 * @param {boolean} disabled - 是否禁用
 */
function setButtonState(button, disabled) {
    if (button) {
        button.disabled = disabled;
        button.classList.toggle('disabled', disabled);
        if (disabled) {
            button.setAttribute('aria-disabled', 'true');
        } else {
            button.removeAttribute('aria-disabled');
        }
    }
}

/**
 * 生成剪纸图案
 */
window.generatePattern = async function() {
    const prompt = document.getElementById('prompt')?.value;
    if (!prompt) {
        showMessage('请输入关键词', 'danger');
        return;
    }

    const generateBtn = document.querySelector('.search-box .btn');
    const patternImageContainer = document.getElementById('patternImage');
    const stepsListContainer = document.getElementById('stepsList');

    if (!generateBtn || !patternImageContainer || !stepsListContainer) {
        showMessage('页面元素加载失败', 'danger');
        return;
    }

    const originalButtonText = generateBtn.innerHTML;

    try {
        // 更新按钮状态并显示加载动画
        generateBtn.innerHTML = '<span class="spinner"></span> 生成中...';
        setButtonState(generateBtn, true);
        
        const loadingHTML = '<div class="loading-placeholder"><div class="spinner-large"></div><p>正在加载，请稍候...</p></div>';
        patternImageContainer.innerHTML = loadingHTML;
        stepsListContainer.innerHTML = loadingHTML;

        // 显示结果和控制区域
        const resultSection = document.getElementById('resultSection');
        const controlSection = document.getElementById('controlSection');
        if(resultSection) resultSection.style.display = 'block';
        if(controlSection) controlSection.style.display = 'block';

        // 发送生成请求
        const response = await fetch('/generate_pattern', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt: prompt })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '生成图案失败');
        }

        const data = await response.json();
        if (!data || !data.image) {
            throw new Error('从服务器返回的图案数据无效');
        }

        // 更新图案显示
        currentPattern = data.image;
        patternImageContainer.innerHTML = `<img src="data:image/png;base64,${data.image}" alt="生成的图案">`;

        // 分析剪纸步骤
        await analyzeSteps(data.image, stepsListContainer, loadingHTML);

    } catch (error) {
        console.error('生成图案过程中发生错误:', error);
        showMessage(error.message || '生成图案失败', 'danger');
        patternImageContainer.innerHTML = `
            <div class="error-container">
                <p class="text-center error-message">图案加载失败</p>
                <div class="file-upload">
                    <input type="file" id="patternUpload" accept="image/*" onchange="handlePatternUpload(event)" class="file-input">
                    <label for="patternUpload" class="file-label">
                        <span class="upload-icon">📁</span>
                        <span>上传图片</span>
                    </label>
                </div>
            </div>`;
        stepsListContainer.innerHTML = '<p class="text-center error-message">步骤加载失败。</p>';
    } finally {
        // 恢复按钮状态
        generateBtn.innerHTML = originalButtonText;
        setButtonState(generateBtn, false);
    }
};

/**
 * 分析剪纸步骤
 * @param {string} imageData - 图案的base64数据
 * @param {HTMLElement} stepsListContainer - 步骤列表容器
 * @param {string} loadingHTML - 加载动画HTML
 */
async function analyzeSteps(imageData, stepsListContainer, loadingHTML) {
    try {
        if (!imageData) {
            showMessage('没有图像数据可供分析', 'danger');
            stepsListContainer.innerHTML = '<p class="text-center error-message">无法分析步骤：无图像数据。</p>';
            return;
        }

        // 发送分析请求
        const response = await fetch('/analyze_steps', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: imageData })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '分析步骤失败');
        }

        const data = await response.json();
        
        // 检查返回的数据格式
        if (!data || typeof data !== 'object') {
            throw new Error('服务器返回的数据格式无效');
        }

        // 检查steps字段
        if (!data.steps || !Array.isArray(data.steps) || data.steps.length === 0) {
            throw new Error('未能生成有效的剪纸步骤');
        }

        // 更新步骤显示
        currentSteps = data.steps;
        
        // 保存SVG数据和可视化图像
        if (data.svg_data) {
            currentSVG = data.svg_data;
        }
        if (data.visualization) {
            currentVisualization = data.visualization;
        }

        // 更新显示
        updateVisualizationDisplay(stepsListContainer);

        showMessage(`成功生成剪纸分析结果`, 'success');

    } catch (error) {
        console.error('分析步骤过程中发生错误:', error);
        showErrorModal(error.message || '分析步骤失败');
        stepsListContainer.innerHTML = `
            <div class="error-container">
                <p class="text-center error-message">步骤分析失败: ${error.message}</p>
                <button onclick="retryAnalysis()" class="btn btn-primary">重试分析</button>
            </div>`;
    }
}

/**
 * 重试分析
 */
window.retryAnalysis = async function() {
    const patternImage = document.querySelector('#patternImage img');
    if (!patternImage || !patternImage.src) {
        showMessage('没有可分析的图案', 'warning');
        return;
    }

    const stepsListContainer = document.getElementById('stepsList');
    const loadingHTML = '<div class="loading-placeholder"><div class="spinner-large"></div><p>正在重新分析步骤...</p></div>';
    if(stepsListContainer) stepsListContainer.innerHTML = loadingHTML;
    
    // 从图片的 src 中获取 base64 数据
    const imageData = patternImage.src.split(',')[1];
    await analyzeSteps(imageData, stepsListContainer, loadingHTML);
}

/**
 * 更新可视化显示
 * @param {HTMLElement} container - 显示容器
 */
function updateVisualizationDisplay(container) {
    if (!container) return;

    if (viewMode === 'visualization' && currentVisualization) {
        container.innerHTML = `
            <div class="visualization-container">
                <img src="data:image/png;base64,${currentVisualization}" alt="剪纸步骤可视化" class="visualization-image">
            </div>`;
    } else if (viewMode === 'svg' && currentSVG) {
        container.innerHTML = `
            <div class="svg-container">
                ${currentSVG}
            </div>`;
    } else {
        container.innerHTML = '<p class="text-center">暂无可视化数据</p>';
    }
}

/**
 * 切换步骤视图
 */
function switchToStepsView() {
    try {
        // 检查是否有当前图案和步骤数据
        if (!currentPattern) {
            showMessage('请先生成图案', 'warning');
            return;
        }

        if (!currentSteps || currentSteps.length === 0) {
            showMessage('请先生成步骤', 'warning');
            return;
        }

        const patternView = document.getElementById('patternView');
        const stepsView = document.getElementById('stepsView');
        const switchToStepsBtn = document.getElementById('switchToStepsBtn');
        const switchToPatternBtn = document.getElementById('switchToPatternBtn');

        if (!patternView || !stepsView || !switchToStepsBtn || !switchToPatternBtn) {
            showMessage('页面元素加载失败', 'danger');
            return;
        }

        // 更新视图状态
        currentView = 'steps';
        patternView.style.display = 'none';
        stepsView.style.display = 'block';
        
        // 更新按钮状态
        switchToStepsBtn.classList.add('active');
        switchToPatternBtn.classList.remove('active');
        
        // 更新步骤显示
        updateStepsDisplay(currentSteps);
        
        // 滚动到视图顶部
        stepsView.scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('切换到步骤视图时发生错误:', error);
        showErrorModal('切换视图失败: ' + error.message);
    }
}

/**
 * 切换到SVG视图
 */
function switchToPatternView() {
    try {
        // 检查是否有当前图案
        if (!currentPattern) {
            showMessage('请先生成图案', 'warning');
            return;
        }

        // 检查是否有SVG数据
        if (!currentSVG) {
            showMessage('请先生成步骤以获取SVG数据', 'warning');
            return;
        }

        // 更新视图状态
        currentView = 'pattern';
        document.getElementById('stepsView').style.display = 'none';
        document.getElementById('patternView').style.display = 'block';
        
        // 更新按钮状态
        document.getElementById('switchToPatternBtn').classList.add('active');
        document.getElementById('switchToStepsBtn').classList.remove('active');
        
        // 更新SVG显示
        const patternContainer = document.getElementById('patternContainer');
        if (patternContainer) {
            patternContainer.innerHTML = currentSVG;
        }
        
        // 滚动到视图顶部
        document.getElementById('patternView').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('切换到SVG视图时发生错误:', error);
        showErrorModal('切换视图失败: ' + error.message);
    }
}

/**
 * 切换步骤视图模式
 */
window.toggleStepsView = function() {
    const toggleBtn = document.getElementById('toggleViewBtn');
    if (!toggleBtn) {
        console.error('切换视图按钮未找到');
        return;
    }

    // 移除旧的指示器
    const existingIndicator = document.querySelector('.view-mode-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    // 更新视图模式
    switch (viewMode) {
        case 'visualization':
            viewMode = 'svg';
            toggleBtn.title = '切换到可视化视图';
            break;
        case 'svg':
            viewMode = 'visualization';
            toggleBtn.title = '切换到SVG视图';
            break;
    }
    
    // 更新视图模式指示器
    toggleBtn.classList.add('btn-view-toggle');
    const indicator = document.createElement('span');
    indicator.className = 'view-mode-indicator';
    indicator.textContent = `当前视图: ${getViewModeName(viewMode)}`;
    toggleBtn.appendChild(indicator);
    
    // 更新显示
    const stepsListContainer = document.getElementById('stepsList');
    if (stepsListContainer) {
        updateVisualizationDisplay(stepsListContainer);
    }
}

/**
 * 获取视图模式的中文名称
 * @param {string} mode - 视图模式
 * @returns {string} 视图模式的中文名称
 */
function getViewModeName(mode) {
    const modeNames = {
        'visualization': '可视化视图',
        'svg': 'SVG视图'
    };
    return modeNames[mode] || mode;
}

/**
 * 下载图案
 */
window.downloadPattern = function() {
    try {
        let data, filename, type;
        
        if (viewMode === 'visualization' && currentVisualization) {
            data = `data:image/png;base64,${currentVisualization}`;
            filename = '剪纸步骤可视化.png';
            type = 'image/png';
        } else if (viewMode === 'svg' && currentSVG) {
            // 将SVG转换为Blob
            const svgBlob = new Blob([currentSVG], { type: 'image/svg+xml;charset=utf-8' });
            data = URL.createObjectURL(svgBlob);
            filename = '剪纸步骤.svg';
            type = 'image/svg+xml';
        } else {
            showMessage('没有可下载的数据', 'warning');
            return;
        }

        const link = document.createElement('a');
        link.href = data;
        link.download = filename;
        link.type = type;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // 如果是SVG，需要清理创建的URL
        if (viewMode === 'svg') {
            URL.revokeObjectURL(data);
        }

        showMessage('下载成功');
    } catch (error) {
        console.error('下载图案时发生错误:', error);
        showMessage('下载失败', 'danger');
    }
}

/**
 * 打印图案
 */
window.printPattern = function() {
    try {
        let content;
        
        if (viewMode === 'visualization' && currentVisualization) {
            content = `
                <html>
                    <head>
                        <title>打印剪纸步骤可视化</title>
                        <style>
                            body { 
                                text-align: center; 
                                margin: 0;
                                padding: 20px;
                            }
                            img { 
                                max-width: 100%; 
                                height: auto;
                                display: block;
                                margin: 0 auto;
                            }
                            @media print {
                                body { padding: 0; }
                                img { max-width: 100%; }
                            }
                        </style>
                    </head>
                    <body>
                        <img src="data:image/png;base64,${currentVisualization}" alt="剪纸步骤可视化">
                    </body>
                </html>`;
        } else if (viewMode === 'svg' && currentSVG) {
            content = `
                <html>
                    <head>
                        <title>打印剪纸步骤SVG</title>
                        <style>
                            body { 
                                text-align: center; 
                                margin: 0;
                                padding: 20px;
                            }
                            svg { 
                                max-width: 100%; 
                                height: auto;
                                display: block;
                                margin: 0 auto;
                            }
                            @media print {
                                body { padding: 0; }
                                svg { max-width: 100%; }
                            }
                        </style>
                    </head>
                    <body>
                        ${currentSVG}
                    </body>
                </html>`;
        } else {
            showMessage('没有可打印的数据', 'warning');
            return;
        }

        const printWindow = window.open('', '_blank');
        printWindow.document.write(content);
        printWindow.document.close();
        
        // 等待图片加载完成后再打印
        printWindow.onload = function() {
            printWindow.print();
            // 打印完成后关闭窗口
            printWindow.onafterprint = function() {
                printWindow.close();
            };
        };
    } catch (error) {
        console.error('打印图案时发生错误:', error);
        showMessage('打印失败', 'danger');
    }
}

/**
 * 下载步骤
 */
window.downloadSteps = function() {
    if (!currentSteps || !Array.isArray(currentSteps)) {
        showMessage('没有可下载的步骤', 'warning');
        return;
    }

    try {
        const stepsText = currentSteps.map((step, index) => 
            `步骤 ${step.step || index + 1}:\n${step.description || '无描述'}\n\n`
        ).join('');

        const blob = new Blob([stepsText], { type: 'text/plain;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = '剪纸步骤.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showMessage('步骤下载成功', 'success');
    } catch (error) {
        console.error('下载步骤时发生错误:', error);
        showErrorModal('下载步骤失败，请重试');
    }
}

/**
 * 开始切割
 */
window.startCutting = async function() {
    if (!currentSteps || !Array.isArray(currentSteps)) {
        showMessage('没有可执行的切割步骤', 'warning');
        return;
    }

    // 检查Arduino连接状态
    try {
        const connectionCheck = await fetch('/check_arduino_connection');
        if (!connectionCheck.ok) {
            throw new Error('Arduino未连接');
        }
    } catch (error) {
        showMessage('请确保Arduino已正确连接', 'danger');
        return;
    }

    showConfirmModal('确定要开始切割吗？', async () => {
        try {
            isCutting = true;
            isPaused = false; // 重置暂停状态
            const startBtn = document.querySelector('button[onclick="startCutting()"]');
            const pauseBtn = document.querySelector('button[onclick="pauseCutting()"]');
            const stopBtn = document.querySelector('button[onclick="stopCutting()"]');

            if (startBtn) setButtonState(startBtn, true);
            if (pauseBtn) setButtonState(pauseBtn, false);
            if (stopBtn) setButtonState(stopBtn, false);

            const response = await fetch('/send_to_arduino', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(currentSteps)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '发送切割指令失败');
            }

            showMessage('切割指令已发送到机器', 'success');
        } catch (error) {
            console.error('开始切割时发生错误:', error);
            showErrorModal(error.message || '开始切割失败');
            isCutting = false;
            const startBtn = document.querySelector('button[onclick="startCutting()"]');
            if (startBtn) setButtonState(startBtn, false);
        }
    });
}

/**
 * 暂停切割
 */
window.pauseCutting = function() {
    if (!isCutting) {
        showMessage('当前没有正在进行的切割任务', 'warning');
        return;
    }

    isPaused = !isPaused;
    const pauseBtn = document.querySelector('button[onclick="pauseCutting()"]');
    pauseBtn.textContent = isPaused ? '继续' : '暂停';
    showMessage(isPaused ? '切割已暂停' : '切割已继续', 'success');
}

/**
 * 停止切割
 */
window.stopCutting = function() {
    if (!isCutting) {
        showMessage('当前没有正在进行的切割任务', 'warning');
        return;
    }

    showConfirmModal('确定要停止切割吗？', () => {
        isCutting = false;
        isPaused = false;
        
        const startBtn = document.querySelector('button[onclick="startCutting()"]');
        const pauseBtn = document.querySelector('button[onclick="pauseCutting()"]');
        const stopBtn = document.querySelector('button[onclick="stopCutting()"]');

        setButtonState(startBtn, false);
        setButtonState(pauseBtn, true);
        setButtonState(stopBtn, true);
        
        showMessage('切割已停止', 'success');
    });
}

/**
 * 处理图案上传
 * @param {Event} event - 文件上传事件
 */
window.handlePatternUpload = async function(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 验证文件类型和大小
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];

    if (!file.type.startsWith('image/')) {
        showMessage('请上传图片文件', 'danger');
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        showMessage('图片大小不能超过5MB', 'danger');
        return;
    }

    if (!allowedTypes.includes(file.type)) {
        showMessage('请上传JPG、PNG或GIF格式的图片', 'danger');
        return;
    }

    try {
        const reader = new FileReader();
        reader.onload = async function(e) {
            const imageData = e.target.result;
            const base64Data = imageData.split(',')[1];
            
            const patternImageContainer = document.getElementById('patternImage');
            const stepsListContainer = document.getElementById('stepsList');
            
            if (patternImageContainer) {
                patternImageContainer.innerHTML = `<img src="${imageData}" alt="上传的图案">`;
            }

            if (stepsListContainer) {
                const loadingHTML = '<div class="loading-placeholder"><div class="spinner-large"></div><p>正在分析步骤...</p></div>';
                stepsListContainer.innerHTML = loadingHTML;
                await analyzeSteps(base64Data, stepsListContainer, loadingHTML);
            }
        };
        reader.readAsDataURL(file);
    } catch (error) {
        console.error('处理上传图片时发生错误:', error);
        showMessage('处理图片失败', 'danger');
    }
};

// 添加键盘事件监听
document.addEventListener('DOMContentLoaded', function() {
    const promptInput = document.getElementById('prompt');
    if (promptInput) {
        promptInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                generatePattern();
            }
        });
    }
}); 