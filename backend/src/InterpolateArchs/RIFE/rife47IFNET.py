"""
MIT License

Copyright (c) 2024 Hzwer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import torch
import torch.nn as nn
import math


try:
    from .interpolate import interpolate
except:
    from torch.nn.functional import interpolate


def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
    return nn.Sequential(
        nn.Conv2d(
            in_planes,
            out_planes,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=True,
        ),
        nn.LeakyReLU(0.2, True),
    )


def conv_bn(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
    return nn.Sequential(
        nn.Conv2d(
            in_planes,
            out_planes,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
            bias=False,
        ),
        nn.BatchNorm2d(out_planes),
        nn.LeakyReLU(0.2, True),
    )


class MyPixelShuffle(nn.Module):
    def __init__(self, upscale_factor):
        super(MyPixelShuffle, self).__init__()
        self.upscale_factor = upscale_factor

    def forward(self, x):
        b, c, hh, hw = x.size()
        out_channel = c // (self.upscale_factor**2)
        h = hh * self.upscale_factor
        w = hw * self.upscale_factor
        x_view = x.view(
            b, out_channel, self.upscale_factor, self.upscale_factor, hh, hw
        )
        return x_view.permute(0, 1, 4, 2, 5, 3).reshape(b, out_channel, h, w)


class ResConv(nn.Module):
    def __init__(self, c, dilation=1):
        super(ResConv, self).__init__()
        self.conv = nn.Conv2d(c, c, 3, 1, dilation, dilation=dilation, groups=1)
        self.beta = nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
        self.relu = nn.LeakyReLU(0.2, True)

    def forward(self, x):
        return self.relu(self.conv(x) * self.beta + x)


class IFBlock(nn.Module):
    def __init__(self, in_planes, c=64):
        super(IFBlock, self).__init__()
        self.conv0 = nn.Sequential(
            conv(in_planes, c // 2, 3, 2, 1),
            conv(c // 2, c, 3, 2, 1),
        )
        self.convblock = nn.Sequential(
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
            ResConv(c),
        )
        self.lastconv = nn.Sequential(
            nn.ConvTranspose2d(c, 4 * 6, 4, 2, 1), nn.PixelShuffle(2)
        )

    def forward(self, x, flow=None, scale=1):
        x = interpolate(
            x, scale_factor=1.0 / scale, mode="bilinear", align_corners=False
        )
        if flow is not None:
            flow = (
                interpolate(
                    flow, scale_factor=1.0 / scale, mode="bilinear", align_corners=False
                )
                / scale
            )
            x = torch.cat((x, flow), 1)
        feat = self.conv0(x)
        feat = self.convblock(feat)
        tmp = self.lastconv(feat)
        tmp = interpolate(tmp, scale_factor=scale, mode="bilinear", align_corners=False)
        flow = tmp[:, :4] * scale
        mask = tmp[:, 4:5]
        return flow, mask


class IFNet(nn.Module):
    def __init__(
        self,
        scale=1.0,
        ensemble=False,
        dtype=torch.float32,
        device="cuda",
        width=1920,
        height=1080,
        rife_trt_mode="accurate",
    ):
        super(IFNet, self).__init__()
        self.block0 = IFBlock(7 + 8, c=192)
        self.block1 = IFBlock(8 + 4 + 8, c=128)
        self.block2 = IFBlock(8 + 4 + 8, c=96)
        self.block3 = IFBlock(8 + 4 + 8, c=64)
        self.encode = nn.Sequential(
            nn.Conv2d(3, 16, 3, 2, 1), nn.ConvTranspose2d(16, 4, 4, 2, 1)
        )
        self.device = device
        self.dtype = dtype
        self.scale_list = [8 / scale, 4 / scale, 2 / scale, 1 / scale]
        self.ensemble = ensemble
        self.width = width
        self.height = height
        self.block = [self.block0, self.block1, self.block2, self.block3]
        # self.contextnet = Contextnet()
        # self.unet = Unet()
        if rife_trt_mode == "fast":
            from .warplayer import warp
        elif rife_trt_mode == "accurate":
            try:
                from .custom_warplayer import warp
            except:
                from .warplayer import warp
        else:
            raise ValueError("rife_trt_mode must be 'fast' or 'accurate'")
        self.warp = warp

    def forward(self, img0, img1, timestep, tenFlow_div, backwarp_tenGrid, f0, f1):
        warped_img0 = img0
        warped_img1 = img1
        flow = None
        mask = None

        for i in range(4):
            if flow is None:
                flow, mask = self.block[i](
                    torch.cat((img0, img1, f0, f1, timestep), 1),
                    None,
                    scale=self.scale_list[i],
                )
                if self.ensemble:
                    f_, m_ = self.block[i](
                        torch.cat((img1, img0, f1, f0, 1 - timestep), 1),
                        None,
                        scale=self.scale_list[i],
                    )
                    flow = (flow + torch.cat((f_[:, 2:4], f_[:, :2]), 1)) / 2
                    mask = (mask + (-m_)) / 2
            else:
                wf0 = self.warp(f0, flow[:, :2], tenFlow_div, backwarp_tenGrid)
                wf1 = self.warp(f1, flow[:, 2:4], tenFlow_div, backwarp_tenGrid)
                fd, m0 = self.block[i](
                    torch.cat(
                        (
                            warped_img0,
                            warped_img1,
                            wf0,
                            wf1,
                            timestep,
                            mask,
                        ),
                        1,
                    ),
                    flow,
                    scale=self.scale_list[i],
                )
                if self.ensemble:
                    f_, m_ = self.block[i](
                        torch.cat(
                            (
                                warped_img1,
                                warped_img0,
                                wf1,
                                wf0,
                                1 - timestep,
                                -mask,
                            ),
                            1,
                        ),
                        torch.cat((flow[:, 2:4], flow[:, :2]), 1),
                        scale=self.scale_list[i],
                    )
                    fd = (fd + torch.cat((f_[:, 2:4], f_[:, :2]), 1)) / 2
                    mask = (m0 + (-m_)) / 2
                else:
                    mask = m0
                flow = flow + fd
            warped_img0 = self.warp(img0, flow[:, :2], tenFlow_div, backwarp_tenGrid)
            warped_img1 = self.warp(img1, flow[:, 2:4], tenFlow_div, backwarp_tenGrid)
        mask = torch.sigmoid(mask)
        return (
            (warped_img0 * mask + warped_img1 * (1 - mask))[  # maybe try padding here
                :, :, : self.height, : self.width
            ][0]
            .permute(1, 2, 0)
            .mul(255)
        )
