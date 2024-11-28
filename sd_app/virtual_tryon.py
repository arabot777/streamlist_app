import time
import streamlit as st
import requests
import zipfile
import io
from utils import icon
from streamlit_image_select import image_select
import jwt
import os
import base64

# UI configurations
st.set_page_config(
    page_title="虚拟试穿", page_icon=":bridge_at_night:", layout="wide"
)
icon.show_icon(":bird:")
st.markdown("# :rainbow[AI一键换装]")

KELING_API_URL = "https://api.klingai.com"
AK = os.getenv("KELING_AK", "")
SK = os.getenv("KELING_SK", "")
# 用户名和密码的默认值
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "123456"

# Placeholders for images and gallery
generated_images_placeholder = st.empty()
gallery_placeholder = st.empty()


# 将图片编码为 Base64 格式
def get_base64_of_bin_file(data):
    return base64.b64encode(data).decode()


def encode_jwt_token(ak, sk):
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,  # 有效时间，此处示例代表当前时间+1800s(30min)
        "nbf": int(time.time()) - 5  # 开始生效的时间，此处示例代表当前时间-5秒
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token


def login_page():
    with st.form("login_form"):
        st.title("登录")
        username = st.text_input("用户名", value="")
        password = st.text_input("密码", value="", type="password")
        submit = st.form_submit_button("登录")

        if submit:
            if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
                st.success("登录成功！")
                # 更新会话状态为已登录
                st.session_state.logged_in = True
                st.rerun()  # 重新运行脚本以显示主页面
            else:
                st.error("用户名或密码错误，请重新输入。")


def fetch_checkpoints(api_url: str) -> list:
    """
    Fetch checkpoints from the backend API.

    Args:
        api_url (str): The URL of the backend API to fetch checkpoints from.

    Returns:
        list: A list of checkpoints.
    """
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        # return data.get("checkpoints", [])
        return {
            item["name"]: item["model_version_uuid"]
            for item in data.get("data", []).get("item", [])
        }
    except requests.RequestException as e:
        st.error(f"Failed to fetch checkpoints: {e}")
        return []


def fetch_sampler(api_url: str) -> list:
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        return data.get("data", []).get("item", [])
    except requests.RequestException as e:
        st.error(f"Failed to fetch sampler: {e}")
        return []


def configure_sidebar() -> None:
    """
    Setup and display the sidebar elements.

    This function configures the sidebar of the Streamlit application,
    including the form for user inputs and the resources section.
    """

    checkpoints = ["kolors-virtual-try-on-v1"]
    with st.sidebar:
        with st.form("my_form"):
            st.info("**虚拟试穿 ↓**", icon="👔")
            checkpoint_name = st.selectbox("基础模型", checkpoints)
            checkPointId = checkpoint_name
            # Advanced Settings (for the curious minds!)
            image_human = st.file_uploader("上传人物图片")
            image_clothes = st.file_uploader("上传衣服图片")
            # The Big Red "Submit" Button!
            submitted = st.form_submit_button(
                "Submit", type="primary", use_container_width=True
            )

        # Credits and resources
        st.divider()
        
        return (
            submitted,
            checkPointId,
            image_human,
            image_clothes,
        )


def main_page(
    submitted: bool,
    checkPointId: str,
    image_human: str,
    image_clothes: str,
) -> None:
    if submitted:
        with st.status(
            "👩🏾‍🍳 Whipping up your words into art...", expanded=True
        ) as status:
            st.write("⚙️ Model initiated")
            st.write("🙆‍♀️ Stand up and strecth in the meantime")
            try:
                with generated_images_placeholder.container():
                    # 调用后端接口以获取任务的 UUID
                    st.write("本次任务的输入为：")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image(image_human, caption="人物图片 🧍‍♂️", width=300)
                    with col2:
                        st.image(image_clothes, caption="衣服图片 👗", width=300)
                    st.write("🚀 开始虚拟试穿...")
                    st.write("🔥 请稍等片刻，正在生成中...")

                    token = encode_jwt_token(AK, SK)
                    # st.write(image_human)
                    # 支持传入图片Base64编码或图片URL
                    
                    human_image_base64 = get_base64_of_bin_file(image_human.getvalue())
                    clothes_image_base64 = get_base64_of_bin_file(image_clothes.getvalue())
                    # st.write(human_image_base64)
                    response = requests.post(
                        KELING_API_URL + "/v1/images/kolors-virtual-try-on",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "model_name": checkPointId,
                            "human_image": human_image_base64,
                            "cloth_image": clothes_image_base64,
                        },
                    )
                    response.raise_for_status()
                    task_id = response.json().get("data").get("task_id")
                    st.session_state.task_id = task_id
                    st.write(f"当前正在试穿的任务id: {task_id}")
                    # CjiIomdAMX8AAAAAARAC_g
                    # 轮询后端接口以获取生成的图片
                    all_images = []
                    while True:
                        result_response = requests.get(
                            f"{KELING_API_URL}/v1/images/kolors-virtual-try-on/{task_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        result_response.raise_for_status()
                        result_data = result_response.json()
                        if result_data.get("data").get("task_status") == "succeed":
                            task_result = result_data.get("data", {}).get("task_result", {})
                            for image in task_result.get("images", []):
                                all_images.append(image.get("url"))

                            break
                        
                        time.sleep(2)  # 等待 5 秒后再次轮询
                    
                    result_images = []
                    if all_images:
                        st.toast("Your image has been generated!", icon="😍")
                        st.session_state.generated_image = all_images

                        # Displaying the image
                        for image in st.session_state.generated_image:
                            with st.container():
                                st.image(
                                    image,
                                    caption="Generated Image 🎈",
                                    use_column_width=True,
                                )
                                response = requests.get(image)
                                if response.status_code == 200:
                                    image_data = response.content
                                    result_images.append(image_data)
                                else:
                                    st.error(
                                        f"Failed to fetch image from {image}. Error code: {response.status_code}",
                                        icon="🚨",
                                    )

                        # Create a BytesIO object
                        zip_io = io.BytesIO()

                        # Download option for each image
                        with zipfile.ZipFile(zip_io, "w") as zipf:
                            for i, image_data in enumerate(result_images):
                                zipf.writestr(f"output_file_{i+1}.png", image_data)

                        # Create a download button for the zip file
                        st.download_button(
                            ":red[**Download the Images**]",
                            data=zip_io.getvalue(),
                            file_name="output_files.zip",
                            mime="application/zip",
                            use_container_width=True,
                        )
                    
                status.update(
                    label="✅ Images generated!", state="complete", expanded=False
                )
            except Exception as e:
                print(e)
                st.error(f"Encountered an error: {e}", icon="🚨")

    # If not submitted, chill here 🍹
    else:
        pass

    # Gallery display for inspo
    with gallery_placeholder.container():
        st.write("🎨 **往期生成记录**")
        token = encode_jwt_token(AK, SK)
        response = requests.get(
            f"{KELING_API_URL}/v1/images/kolors-virtual-try-on",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()

        images = []
        for task in data.get("data", []):
            task_result = task.get("task_result", {})
            for image in task_result.get("images", []):
                images.append(image.get("url"))

        images = images[:10]
        image_select(
            label="～ 😉",
            images=images,
            use_container_width=True,
        )


def main():
    """
    Main function to run the Streamlit application.

    This function initializes the sidebar configuration and the main page layout.
    It retrieves the user inputs from the sidebar, and passes them to the main page function.
    The main page function then generates images based on these inputs.
    """
    (
        submitted,
        checkPointId,
        image_human,
        image_clothes,
    ) = configure_sidebar()
    main_page(
        submitted,
        checkPointId,
        image_human,
        image_clothes,
    )


# 检查会话状态中是否有登录状态，如果没有，初始化为 False
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if __name__ == "__main__":
    main()
    # if st.session_state.logged_in:
    #     main()
    # else:
    #     login_page()