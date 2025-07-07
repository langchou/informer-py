// 页面加载完成后执行
$(document).ready(function() {
    // 初始化Bootstrap的工具提示
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 显示提示信息
    function showAlert(message, type = 'success') {
        $('#alertMessage').text(message);
        $('#alertBox').removeClass('d-none alert-success alert-danger')
            .addClass('show alert-' + type);
        
        // 3秒后自动隐藏
        setTimeout(function() {
            $('#alertBox').removeClass('show').addClass('d-none');
        }, 3000);
    }

    // 保存日志配置
    $('#saveLogConfig').click(function() {
        const formData = {
            file: $('#logConfigForm input[name="file"]').val(),
            max_size: parseInt($('#logConfigForm input[name="max_size"]').val()),
            max_backups: parseInt($('#logConfigForm input[name="max_backups"]').val()),
            max_age: parseInt($('#logConfigForm input[name="max_age"]').val()),
            compress: $('#logConfigForm input[name="compress"]').is(':checked'),
            level: $('#logConfigForm select[name="level"]').val()
        };

        $.ajax({
            url: '/update_log_config',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 保存代理配置
    $('#saveProxyConfig').click(function() {
        const formData = {
            proxy_pool_api: $('#proxyConfigForm input[name="proxy_pool_api"]').val()
        };

        $.ajax({
            url: '/update_proxy_config',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 保存Cookies配置
    $('#saveCookies').click(function() {
        const formData = {
            cookies: $('#cookiesForm textarea[name="cookies"]').val()
        };

        $.ajax({
            url: '/update_cookies',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 保存等待时间配置
    $('#saveWaitTime').click(function() {
        const min = parseInt($('#waitTimeForm input[name="min"]').val());
        const max = parseInt($('#waitTimeForm input[name="max"]').val());
        
        if (min > max) {
            showAlert('最小时间不能大于最大时间', 'danger');
            return;
        }
        
        const formData = {
            min: min,
            max: max
        };

        $.ajax({
            url: '/update_wait_time',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 保存LLM配置
    $('#saveLlmConfig').click(function() {
        const formData = {
            api_key: $('#llmConfigForm input[name="api_key"]').val(),
            base_url: $('#llmConfigForm input[name="base_url"]').val(),
            model: $('#llmConfigForm input[name="model"]').val()
        };

        $.ajax({
            url: '/update_llm_config',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 添加机器人按钮点击事件
    $('#addRobotBtn').click(function() {
        $('#addRobotModal').modal('show');
    });

    // 提交添加机器人表单
    $('#submitAddRobot').click(function() {
        const formData = {
            name: $('#addRobotForm input[name="name"]').val(),
            token: $('#addRobotForm input[name="token"]').val(),
            secret: $('#addRobotForm input[name="secret"]').val(),
            receive_all: $('#addRobotForm input[name="receive_all"]').is(':checked')
        };

        $.ajax({
            url: '/add_robot',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                    $('#addRobotModal').modal('hide');
                    // 重新加载页面以显示新机器人
                    location.reload();
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('添加失败，请检查网络连接', 'danger');
            }
        });
    });

    // 添加用户按钮点击事件
    $('.add-user').click(function() {
        const robotIndex = $(this).data('robot-index');
        $('#robotIndexForUser').val(robotIndex);
        $('#addUserModal').modal('show');
    });

    // 提交添加用户表单
    $('#submitAddUser').click(function() {
        const formData = {
            robot_index: $('#robotIndexForUser').val(),
            phone: $('#addUserForm input[name="phone"]').val(),
            always_at: $('#addUserForm input[name="always_at"]').is(':checked')
        };

        $.ajax({
            url: '/add_user',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                    $('#addUserModal').modal('hide');
                    // 重新加载页面以显示新用户
                    location.reload();
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('添加失败，请检查网络连接', 'danger');
            }
        });
    });

    // 添加关键词按钮点击事件
    $('.add-keyword').click(function() {
        const robotIndex = $(this).data('robot-index');
        const phone = $(this).data('phone');
        $('#robotIndexForKeyword').val(robotIndex);
        $('#phoneForKeyword').val(phone);
        $('#addKeywordModal').modal('show');
    });

    // 提交添加关键词表单
    $('#submitAddKeyword').click(function() {
        const formData = {
            robot_index: $('#robotIndexForKeyword').val(),
            phone: $('#phoneForKeyword').val(),
            keyword: $('#addKeywordForm input[name="keyword"]').val()
        };

        $.ajax({
            url: '/add_keyword',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                    $('#addKeywordModal').modal('hide');
                    // 重新加载页面以显示新关键词
                    location.reload();
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('添加失败，请检查网络连接', 'danger');
            }
        });
    });

    // 删除关键词按钮点击事件
    $(document).on('click', '.delete-keyword', function() {
        const keyword = $(this).data('keyword');
        const robotIndex = $(this).data('robot-index');
        const phone = $(this).data('phone');
        
        if (confirm(`确定要删除关键词 "${keyword}" 吗？`)) {
            const formData = {
                robot_index: robotIndex,
                phone: phone,
                keyword: keyword
            };

            $.ajax({
                url: '/delete_keyword',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(formData),
                success: function(response) {
                    if (response.status === 'success') {
                        showAlert(response.message);
                        // 重新加载页面以显示更新
                        location.reload();
                    } else {
                        showAlert(response.message, 'danger');
                    }
                },
                error: function() {
                    showAlert('删除失败，请检查网络连接', 'danger');
                }
            });
        }
    });

    // 保存机器人配置
    $('.save-robot').click(function() {
        const form = $(this).closest('form');
        const index = form.data('index');
        const formData = {
            robot_index: index,
            robot_data: {
                name: form.find('input[name="name"]').val(),
                token: form.find('input[name="token"]').val(),
                secret: form.find('input[name="secret"]').val(),
                enabled: form.find('input[name="enabled"]').is(':checked'),
                receive_all: form.find('input[name="receive_all"]').is(':checked')
            }
        };

        $.ajax({
            url: '/update_robot',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.status === 'success') {
                    showAlert(response.message);
                } else {
                    showAlert(response.message, 'danger');
                }
            },
            error: function() {
                showAlert('保存失败，请检查网络连接', 'danger');
            }
        });
    });

    // 删除用户按钮点击事件
    $('.delete-user').click(function() {
        if (confirm('确定要删除此用户吗？')) {
            const robotIndex = $(this).data('robot-index');
            const phone = $(this).data('phone');
            
            $.ajax({
                url: '/delete_user',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    robot_index: robotIndex,
                    phone: phone
                }),
                success: function(response) {
                    if (response.status === 'success') {
                        showAlert(response.message);
                        // 重新加载页面以更新用户列表
                        location.reload();
                    } else {
                        showAlert(response.message, 'danger');
                    }
                },
                error: function() {
                    showAlert('删除失败，请检查网络连接', 'danger');
                }
            });
        }
    });

    // 保存全部配置按钮
    $('#saveAllBtn').click(function() {
        // 触发所有保存按钮的点击事件
        $('#saveLogConfig').click();
        $('#saveProxyConfig').click();
        $('#saveCookies').click();
        $('#saveWaitTime').click();
        $('#saveLlmConfig').click();
        
        showAlert('已触发所有配置的保存操作');
    });
}); 